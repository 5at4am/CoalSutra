"""Dashboard metrics endpoint: aggregate counts, review flag % and latency."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import ConflictFlag, Document, ExtractedFact
from app.models.enums import ConflictStatus, DocumentStatus, SourceType
from app.services import query_metrics


def _seed_document(factory, filename: str, status=DocumentStatus.processed) -> int:
    with factory() as session:
        doc = Document(
            filename=filename,
            source_type=SourceType.digital_pdf,
            status=status,
            raw_file_path=f"/tmp/{filename}",
        )
        session.add(doc)
        session.commit()
        return doc.id


def _seed_fact(factory, document_id: int, value: str) -> int:
    with factory() as session:
        fact = ExtractedFact(
            document_id=document_id,
            entity="coal_reserve",
            value=value,
            unit="MT",
            date_reference=date(2019, 1, 1),
            page_number=1,
            raw_snippet=f"coal reserve 2019 {value} MT",
            confidence=0.95,
        )
        session.add(fact)
        session.commit()
        return fact.id


@pytest.fixture()
def client():
    query_metrics.reset()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client, factory

    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def test_metrics_summary_counts_and_percentages(client):
    test_client, factory = client
    _seed_document(factory, "pending.pdf", status=DocumentStatus.pending)
    doc_a = _seed_document(factory, "a.pdf")
    doc_b = _seed_document(factory, "b.pdf")
    _seed_document(factory, "clean.pdf")

    fact_a = _seed_fact(factory, doc_a, "1240")
    fact_b = _seed_fact(factory, doc_b, "938")
    with factory() as session:
        session.add(
            ConflictFlag(fact_a_id=fact_a, fact_b_id=fact_b, reason="value mismatch")
        )
        session.commit()

    body = test_client.get("/api/v1/metrics/summary").json()

    assert body["documents_total"] == 4
    assert body["documents_processed"] == 3
    assert body["open_conflicts"] == 1
    # 2 of 3 processed documents are implicated in the conflict
    assert body["flagged_documents_pct"] == pytest.approx(66.7)
    assert body["avg_query_ms"] is None
    assert body["queries_served"] == 0


def test_metrics_summary_zero_state(client):
    test_client, factory = client
    _seed_document(factory, "fresh.pdf", status=DocumentStatus.pending)

    body = test_client.get("/api/v1/metrics/summary").json()
    assert body["documents_total"] == 1
    assert body["documents_processed"] == 0
    assert body["open_conflicts"] == 0
    assert body["flagged_documents_pct"] == 0.0


def test_metrics_tracks_query_latency(client):
    test_client, factory = client
    query_metrics.record_query(123.4)
    query_metrics.record_query(77.6)

    body = test_client.get("/api/v1/metrics/summary").json()
    assert body["avg_query_ms"] == pytest.approx(100.5)
    assert body["queries_served"] == 2