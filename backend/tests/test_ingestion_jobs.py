"""Tests for the durable ingestion job system (enqueue / retry / resume)."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Document, IngestionJob
from app.models.enums import DocumentStatus, JobStatus, SourceType
from app.services.ingestion import orchestrator as ing
from app.services.ingestion import jobs as jobsvc


def _enable_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", _enable_sqlite_fk)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def _add_document(factory) -> Document:
    with factory() as session:
        doc = Document(
            filename="sample.csv",
            source_type=SourceType.spreadsheet,
            status=DocumentStatus.pending,
            raw_file_path="C:\\tmp\\sample.csv",
        )
        session.add(doc)
        session.commit()
        return doc


def test_enqueue_creates_durable_queued_job(session_factory):
    doc = _add_document(session_factory)

    job = jobsvc.enqueue_ingestion(session_factory(), doc.id)

    assert job.status is JobStatus.queued
    assert job.attempts == 0
    assert job.max_attempts == jobsvc.MAX_RETRIES_DEFAULT
    assert job.next_attempt_at is None


def test_enqueue_is_idempotent_per_document(session_factory):
    doc = _add_document(session_factory)

    first = jobsvc.enqueue_ingestion(session_factory(), doc.id)
    second = jobsvc.enqueue_ingestion(session_factory(), doc.id)

    assert first.id == second.id


def test_successful_job_marks_document_processed(session_factory, sample_csv):
    with session_factory() as session:
        doc = Document(
            filename="sample.csv",
            source_type=SourceType.spreadsheet,
            status=DocumentStatus.pending,
            raw_file_path=str(sample_csv),
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

    job = jobsvc.enqueue_ingestion(session_factory(), doc_id)
    worked = jobsvc.run_job(job.id, session_factory=session_factory)

    assert worked is not None
    assert worked.status is JobStatus.succeeded
    assert worked.attempts == 1
    assert worked.last_error is None
    with session_factory() as session:
        assert session.get(Document, doc_id).status is DocumentStatus.processed


def test_failure_retries_with_backoff_then_gives_up(session_factory, monkeypatch, sample_csv):
    with session_factory() as session:
        doc = Document(
            filename="sample.csv",
            source_type=SourceType.spreadsheet,
            status=DocumentStatus.pending,
            raw_file_path=str(sample_csv),
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

    def boom(*args, **kwargs):
        raise RuntimeError("extractor blew up")

    monkeypatch.setattr(ing, "_extract_pages", boom)

    job = jobsvc.enqueue_ingestion(session_factory(), doc_id)
    job.max_attempts = 2
    with session_factory() as session:
        session.merge(job)
        session.commit()

    after_first = jobsvc.run_job(job.id, session_factory=session_factory)
    assert after_first.status is JobStatus.queued
    assert after_first.attempts == 1
    assert after_first.last_error
    assert after_first.next_attempt_at is not None
    with session_factory() as session:
        assert session.get(Document, doc_id).status is DocumentStatus.pending

    after_second = jobsvc.run_job(job.id, session_factory=session_factory)
    assert after_second.status is JobStatus.failed
    assert after_second.attempts == 2
    with session_factory() as session:
        assert session.get(Document, doc_id).status is DocumentStatus.failed


def test_failed_job_is_immediately_retryable_after_backoff(session_factory, monkeypatch, sample_csv):
    with session_factory() as session:
        doc = Document(
            filename="sample.csv",
            source_type=SourceType.spreadsheet,
            status=DocumentStatus.pending,
            raw_file_path=str(sample_csv),
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return [{"page_number": 1, "text": "digested after retry"}]

    monkeypatch.setattr(ing, "_extract_pages", flaky)

    job = jobsvc.enqueue_ingestion(session_factory(), doc_id)
    jobsvc.run_job(job.id, session_factory=session_factory)
    job.next_attempt_at = None

    final = jobsvc.run_job(job.id, session_factory=session_factory)
    assert final.status is JobStatus.succeeded
    assert final.attempts == 2


def test_drain_queue_runs_due_jobs_only(session_factory, sample_csv):
    with session_factory() as session:
        doc = Document(
            filename="sample.csv",
            source_type=SourceType.spreadsheet,
            status=DocumentStatus.pending,
            raw_file_path=str(sample_csv),
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

    job = jobsvc.enqueue_ingestion(session_factory(), doc_id)
    with session_factory() as session:
        session.get(IngestionJob, job.id).next_attempt_at = (
            jobsvc._now() + timedelta(hours=1)
        )
        session.commit()

    assert jobsvc.drain_queue(session_factory=session_factory, limit=10) == 0
    with session_factory() as session:
        assert session.get(Document, doc_id).status is DocumentStatus.pending

    with session_factory() as session:
        session.get(IngestionJob, job.id).next_attempt_at = None
        session.commit()
    assert jobsvc.drain_queue(session_factory=session_factory, limit=10) == 1
    with session_factory() as session:
        assert session.get(Document, doc_id).status is DocumentStatus.processed


def test_resume_stale_jobs_requeues_midflight_work(session_factory):
    with session_factory() as session:
        doc = Document(
            filename="stuck.png",
            source_type=SourceType.image,
            status=DocumentStatus.processing,
            raw_file_path="C:\\tmp\\stuck.png",
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

    job = jobsvc.enqueue_ingestion(session_factory(), doc_id)
    with session_factory() as session:
        session.get(IngestionJob, job.id).status = JobStatus.running
        session.get(Document, doc_id).status = DocumentStatus.processing
        session.commit()

    result = jobsvc.resume_stale_jobs(session_factory=session_factory)

    assert result == {"requeued": 1, "reset": 1}
    with session_factory() as session:
        assert session.get(IngestionJob, job.id).status is JobStatus.queued
        assert session.get(Document, doc_id).status is DocumentStatus.pending