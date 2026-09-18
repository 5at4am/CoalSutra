"""Durable ingestion job runner: enqueue → execute → retry with backoff.

Replaces fire-and-forget `BackgroundTask(ingest_document, ...)` with a persisted
`IngestionJob` row so nothing is lost on restart:

- `enqueue_ingestion` writes a `queued` row (idempotent per document).
- `run_job` claims + executes one job and updates its status.
- `resume_stale_jobs` re-queues everything that was mid-flight when the process
  stopped (jobs stuck `queued`/`running`, or documents stuck `processing`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Document, IngestionJob
from app.models.enums import DocumentStatus, JobStatus

logger = logging.getLogger(__name__)

BACKOFF_BASE_SECONDS = 5
MAX_RETRIES_DEFAULT = 3
STALE_GRACE_SECONDS = 120


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """Treat naive stored datetimes (SQLite) as UTC for safe comparison."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def enqueue_ingestion(session: Session, document_id: int) -> IngestionJob:
    """Persist a retryable ingestion job for ``document_id`` (no duplicates)."""
    document = session.get(Document, document_id)
    if document is None:
        raise ValueError(f"document {document_id} does not exist")
    existing = (
        session.query(IngestionJob)
        .filter(
            IngestionJob.document_id == document_id,
            IngestionJob.status.in_([JobStatus.queued, JobStatus.running]),
        )
        .first()
    )
    if existing is not None:
        return existing
    job = IngestionJob(
        document_id=document_id,
        status=JobStatus.queued,
        attempts=0,
        max_attempts=MAX_RETRIES_DEFAULT,
    )
    document.status = DocumentStatus.pending
    session.add(job)
    session.commit()
    session.refresh(job)
    logger.info("jobs: enqueued ingestion job %s for document %s", job.id, document_id)
    return job


def run_job(job_id: int, session_factory: Any | None = None) -> IngestionJob | None:
    """Execute one job idempotently (safe to call from a background task).

    `ingest_document` swallows its own failures (it marks the document `failed`
    and returns), so this reads that status to drive retries/backoff.
    """
    from app.services.ingestion.orchestrator import ingest_document

    factory = session_factory or SessionLocal
    session = factory()
    job = session.get(IngestionJob, job_id)
    try:
        if job is None:
            logger.warning("jobs: job %s not found", job_id)
            return None
        if job.status == JobStatus.succeeded:
            return job
        document = session.get(Document, job.document_id)
        if document is None:
            job.status = JobStatus.failed
            job.last_error = "document missing"
            session.commit()
            return job

        job.status = JobStatus.running
        job.attempts += 1
        job.last_error = None
        document.status = DocumentStatus.pending
        session.commit()

        ingest_error: str | None = None
        try:
            ingest_document(job.document_id, session_factory=factory)
        except Exception as exc:  # noqa: BLE001 - retry logic below
            ingest_error = f"{type(exc).__name__}: {exc}"
            logger.warning("jobs: run_job %s crashed during ingest: %s", job.id, ingest_error)

        session.expire_all()
        document = session.get(Document, job.document_id)
        doc_failed = document is None or document.status == DocumentStatus.failed

        if doc_failed:
            job.last_error = ingest_error or "document failed during ingest"
            if job.attempts < job.max_attempts:
                job.status = JobStatus.queued
                job.next_attempt_at = _now() + timedelta(
                    seconds=BACKOFF_BASE_SECONDS * (2 ** (job.attempts - 1))
                )
                if document is not None:
                    document.status = DocumentStatus.pending
            else:
                job.status = JobStatus.failed
                job.next_attempt_at = None
                if document is not None:
                    document.status = DocumentStatus.failed
            session.commit()
            logger.warning(
                "jobs: job %s attempt %d/%d failed: %s",
                job.id,
                job.attempts,
                job.max_attempts,
                job.last_error,
            )
            return job

        job.status = JobStatus.succeeded
        job.last_error = None
        job.next_attempt_at = None
        if document is not None and document.status != DocumentStatus.processed:
            document.status = DocumentStatus.processed
        session.commit()
        logger.info("jobs: job %s succeeded", job.id)
        return job

        job.status = JobStatus.succeeded
        job.next_attempt_at = None
        if document is not None and document.status != DocumentStatus.processed:
            document.status = DocumentStatus.processed
        session.commit()
        logger.info("jobs: job %s succeeded", job.id)
        return job
    except Exception:  # noqa: BLE001
        logger.exception("jobs: run_job %s crashed", job_id)
        session.rollback()
        return job
    finally:
        session.close()


def drain_queue(session_factory: Any | None = None, limit: int = 10) -> int:
    """Execute up to ``limit`` due jobs; return number of jobs executed."""
    factory = session_factory or SessionLocal
    session = factory()
    try:
        due_ids = [
            job.id
            for job in (
                session.query(IngestionJob)
                .filter(IngestionJob.status == JobStatus.queued)
                .order_by(IngestionJob.id.asc())
                .limit(limit)
                .all()
            )
            if job.next_attempt_at is None or _as_utc(job.next_attempt_at) <= _now()
        ]
    finally:
        session.close()

    executed = 0
    for job_id in due_ids:
        run_job(job_id, session_factory=factory)
        executed += 1
    return executed


def resume_stale_jobs(session_factory: Any | None = None) -> dict[str, int]:
    """Re-queue everything mid-flight when the process stopped (startup call)."""
    factory = session_factory or SessionLocal
    session = factory()
    requeued = 0
    reset = 0
    try:
        grace = _now() - timedelta(seconds=STALE_GRACE_SECONDS)
        for job in (
            session.query(IngestionJob)
            .filter(IngestionJob.status.in_([JobStatus.queued, JobStatus.running]))
            .all()
        ):
            if job.status == JobStatus.running or (
                _as_utc(job.updated_at or job.created_at) < grace
            ):
                job.status = JobStatus.queued
                job.next_attempt_at = None
                requeued += 1

        for doc in (
            session.query(Document)
            .filter(Document.status == DocumentStatus.processing)
            .all()
        ):
            doc.status = DocumentStatus.pending
            reset += 1
        session.commit()
    except Exception:  # noqa: BLE001 - startup must never crash the app
        logger.exception("jobs: resume_stale_jobs failed")
        session.rollback()
    finally:
        session.close()
    if requeued or reset:
        logger.info(
            "jobs: startup resume - %d job(s) requeued, %d document(s) reset",
            requeued,
            reset,
        )
    return {"requeued": requeued, "reset": reset}