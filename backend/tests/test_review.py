"""Human-in-the-loop review tests: queue content + resolution endpoints.

Confirms the reviewer can decide an open conflict (which fact is correct →
resolved/dismissed with the verdict recorded) and approve or send-back a draft
report, with the expected status transitions and 404/409 guards.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import ConflictFlag, Document, ExtractedFact, Report
from app.models.enums import ConflictStatus, DocumentStatus, ReportStatus, SourceType


def _seed_document(factory, filename: str) -> int:
    with factory() as session:
        doc = Document(
            filename=filename,
            source_type=SourceType.digital_pdf,
            status=DocumentStatus.processed,
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


def _seed_conflict(factory, status=ConflictStatus.open) -> int:
    doc_a = _seed_document(factory, "first.pdf")
    doc_b = _seed_document(factory, "second.pdf")
    fact_a = _seed_fact(factory, doc_a, "1240")
    fact_b = _seed_fact(factory, doc_b, "938")
    with factory() as session:
        flag = ConflictFlag(
            fact_a_id=fact_a,
            fact_b_id=fact_b,
            reason="coal_reserve 2019 reported as 1240 MT vs 938 MT",
            status=status,
        )
        session.add(flag)
        session.commit()
        return flag.id


def _seed_report(factory, status=ReportStatus.draft) -> int:
    with factory() as session:
        report = Report(
            title="Production Summary",
            template_type="production_summary",
            status=status,
            content={
                "sections": {
                    "overview": {"title": "Overview", "body": "Headline numbers here.", "citations": []}
                }
            },
        )
        session.add(report)
        session.commit()
        return report.id


@pytest.fixture()
def client():
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


def test_queue_joins_open_conflicts_and_draft_reports(client):
    test_client, factory = client
    conflict_id = _seed_conflict(factory)  # open
    _seed_conflict(factory, status=ConflictStatus.resolved)
    report_id = _seed_report(factory, status=ReportStatus.draft)
    _seed_report(factory, status=ReportStatus.final)

    body = test_client.get("/api/v1/review/queue").json()

    assert len(body["conflicts"]) == 1
    conflict = body["conflicts"][0]
    assert conflict["id"] == conflict_id
    assert conflict["fact_a"]["value"] == "1240"
    assert conflict["fact_a"]["document_name"] == "first.pdf"
    assert conflict["fact_b"]["value"] == "938"
    assert conflict["fact_b"]["document_name"] == "second.pdf"
    assert conflict["reason"].startswith("coal_reserve 2019")

    assert len(body["draft_reports"]) == 1
    draft = body["draft_reports"][0]
    assert draft["id"] == report_id
    assert draft["title"] == "Production Summary"
    assert "Headline numbers" in draft["summary"]


def test_resolve_conflict_fact_a_marks_it_correct_and_resolves(client):
    test_client, factory = client
    conflict_id = _seed_conflict(factory)

    resp = test_client.post(
        f"/api/v1/review/conflicts/{conflict_id}/resolve",
        json={"decision": "fact_a", "resolved_by": "reviewer@cil"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolution"] == "fact_a"
    assert body["resolved_by"] == "reviewer@cil"

    open_again = test_client.post(
        f"/api/v1/review/conflicts/{conflict_id}/resolve",
        json={"decision": "fact_b", "resolved_by": "reviewer@cil"},
    )
    assert open_again.status_code == 409


def test_resolve_conflict_neither_dismisses(client):
    test_client, factory = client
    conflict_id = _seed_conflict(factory)

    resp = test_client.post(
        f"/api/v1/review/conflicts/{conflict_id}/resolve",
        json={"decision": "neither", "resolved_by": "reviewer@cil"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dismissed"
    assert body["resolution"] == "neither"


def test_resolve_missing_conflict_404(client):
    test_client, _ = client
    resp = test_client.post(
        "/api/v1/review/conflicts/99999/resolve",
        json={"decision": "fact_a", "resolved_by": "reviewer@cil"},
    )
    assert resp.status_code == 404


def test_report_decision_approve_moves_draft_to_reviewed(client):
    test_client, factory = client
    report_id = _seed_report(factory, status=ReportStatus.draft)

    resp = test_client.post(
        f"/api/v1/review/reports/{report_id}/decision",
        json={"decision": "approve", "comment": "numbers match the source"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "reviewed"

    again = test_client.post(
        f"/api/v1/review/reports/{report_id}/decision", json={"decision": "approve"}
    )
    assert again.status_code == 409


def test_report_decision_send_back_keeps_draft_with_comment(client):
    test_client, factory = client
    report_id = _seed_report(factory, status=ReportStatus.draft)

    resp = test_client.post(
        f"/api/v1/review/reports/{report_id}/decision",
        json={"decision": "send_back", "comment": "fix the trends section"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "draft"
    assert body["review_note"] == "fix the trends section"


def test_report_decision_missing_404(client):
    test_client, _ = client
    resp = test_client.post(
        "/api/v1/review/reports/99999/decision", json={"decision": "approve"}
    )
    assert resp.status_code == 404