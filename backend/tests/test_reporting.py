"""Report generator + exporter + API lifecycle tests.

The LLM is mocked with a deterministic function that re-cites every fact id it
sees in the prompt — so the test verifies the report structure, the citation
format (fact_id / document_name / page_number / snippet), the sources section,
unseen-id rejection, entity filtering, and PDF export — all without a network.
"""

import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import Document, ExtractedFact, Report
from app.models.enums import DocumentStatus, ReportStatus, SourceType
from app.services.reporting.exporter import export_report
from app.services.reporting.generator import SectionDraft, generate_report


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


def _seed_fact(
    factory,
    document_id: int,
    entity: str = "coal_production",
    value: str = "38.5",
    unit: str | None = "MT",
    date_reference=None,
    page: int = 1,
    snippet: str | None = None,
) -> int:
    if date_reference is None:
        date_reference = date(2026, 1, 1)
    with factory() as session:
        fact = ExtractedFact(
            document_id=document_id,
            entity=entity,
            value=value,
            unit=unit,
            date_reference=date_reference,
            page_number=page,
            raw_snippet=snippet or f"{entity} was {value} {unit or ''}".strip(),
            confidence=0.95,
        )
        session.add(fact)
        session.commit()
        return fact.id


def mock_llm(prompt, response_schema):
    fact_ids = [int(m) for m in re.findall(r"\[id=(\d+)\]", prompt)]
    return SectionDraft(
        body="Production stood at 38.5 MT and rose to 40.2 MT during the period.",
        citations=[{"fact_id": fact_id} for fact_id in fact_ids],
    )


def _production_seed(factory):
    doc_id = _seed_document(factory, "production_2026.pdf")
    f1 = _seed_fact(
        factory,
        doc_id,
        value="38.5",
        date_reference=date(2026, 1, 1),
        page=1,
        snippet="monthly production was 38.5 MT",
    )
    f2 = _seed_fact(
        factory,
        doc_id,
        value="40.2",
        date_reference=date(2026, 2, 1),
        page=3,
        snippet="monthly production was 40.2 MT",
    )
    return doc_id, f1, f2


def test_generate_report_saves_draft_with_structured_sections(session_factory):
    _doc_id, f1, f2 = _production_seed(session_factory)

    with session_factory() as session:
        report = generate_report(
            session, "production_summary", {"entities": ["coal_production"]}, llm=mock_llm
        )

        assert report.status == ReportStatus.draft
        assert report.template_type == "production_summary"
        assert report.title == "Production Summary"
        sections = report.content["sections"]
        assert set(sections) == {
            "executive_summary",
            "overview",
            "key_figures",
            "trends",
            "observations",
            "sources",
        }

        # non-automatic sections carry validated citations with the full format
        for key in ("overview", "key_figures", "trends"):
            citations = sections[key]["citations"]
            assert {c["fact_id"] for c in citations} == {f1, f2}
            first = citations[0]
            assert set(first) == {"fact_id", "document_name", "page_number", "snippet"}
            assert first["document_name"] == "production_2026.pdf"
            assert first["page_number"] in (1, 3)
            assert isinstance(first["snippet"], str) and first["snippet"]

        # sources section is automatic and aggregates all citations
        assert sections["sources"]["automatic"] is True
        assert sections["sources"]["citations"]
        assert str(f1) in sections["sources"]["body"]
        assert "No sources cited." not in sections["sources"]["body"]

        # in-scope facts + scope are persisted for the PDF export
        facts = report.content["facts"]
        assert {f["fact_id"] for f in facts} == {f1, f2}
        assert all("raw_snippet" in f and "document_name" in f for f in facts)
        assert report.content["scope"] == {"entities": ["coal_production"]}


def test_generate_report_drops_unseen_citation_ids(session_factory):
    _doc_id, f1, _f2 = _production_seed(session_factory)

    def leaky_llm(prompt, response_schema):
        real_ids = [int(m) for m in re.findall(r"\[id=(\d+)\]", prompt)]
        # fabricates one id that was never provided
        return SectionDraft(
            body="text",
            citations=[{"fact_id": i} for i in real_ids] + [{"fact_id": 99999}],
        )

    with session_factory() as session:
        report = generate_report(session, "production_summary", llm=leaky_llm)

    citations = report.content["sections"]["overview"]["citations"]
    assert {c["fact_id"] for c in citations} == {f1, _f2}
    assert 99999 not in {c["fact_id"] for c in citations}


def test_generate_report_respects_entity_filter(session_factory):
    doc_id = _seed_document(session_factory, "mixed.pdf")
    _seed_fact(session_factory, doc_id, entity="coal_production", value="38.5")
    _seed_fact(session_factory, doc_id, entity="ash_content", value="18", unit="pct")
    prompts = []

    def recording_llm(prompt, response_schema):
        prompts.append(prompt)
        return SectionDraft(body="", citations=[])

    with session_factory() as session:
        generate_report(
            session,
            "production_summary",
            {"entities": ["coal_production"]},
            llm=recording_llm,
        )

    assert prompts
    assert all("ash_content" not in prompt for prompt in prompts)
    assert any("coal_production" in prompt for prompt in prompts)


def test_generate_report_unknown_template(session_factory):
    with session_factory() as session:
        with pytest.raises(KeyError):
            generate_report(session, "not_a_template", llm=mock_llm)


def test_generate_report_llm_disabled_uses_fact_fallback(session_factory):
    from app.core.llm import LLMDisabledError

    _doc_id, f1, f2 = _production_seed(session_factory)

    def no_llm(prompt, response_schema):
        raise LLMDisabledError("LLM_API_KEY is not configured")

    with session_factory() as session:
        report = generate_report(session, "production_summary", llm=no_llm)

    sections = report.content["sections"]
    for key in ("overview", "key_figures", "trends"):
        assert sections[key]["body"].startswith("- [coal_production]")
        citations = sections[key]["citations"]
        assert {c["fact_id"] for c in citations} == {f1, f2}
        assert all(c["snippet"] for c in citations)
    assert sections["sources"]["body"].startswith("1. production_2026.pdf")


def test_exporter_writes_pdf_without_error(session_factory, tmp_path):
    _doc_id, f1, f2 = _production_seed(session_factory)
    with session_factory() as session:
        report = generate_report(session, "production_summary", llm=mock_llm)
        report_id = report.id

    with session_factory() as session:
        report = session.get(Report, report_id)
        out = export_report(report, tmp_path / "report.pdf")

    rendered = Path(out)
    assert rendered.exists()
    assert rendered.read_bytes()[:5] == b"%PDF-"


def test_exporter_persists_generated_facts(session_factory):
    _doc_id, f1, f2 = _production_seed(session_factory)
    with session_factory() as session:
        report = generate_report(
            session, "production_summary", {"entities": ["coal_production"]}, llm=mock_llm
        )
    fact_ids = {f["fact_id"] for f in report.content["facts"]}
    assert fact_ids == {f1, f2}
    assert report.content["scope"] == {"entities": ["coal_production"]}


def test_exporter_analytics_math(session_factory):
    from app.services.reporting.exporter import _analytics, _format_change, _highlight_sentence

    _doc_id, _f1, _f2 = _production_seed(session_factory)
    with session_factory() as session:
        report = generate_report(
            session, "production_summary", {"entities": ["coal_production"]}, llm=mock_llm
        )

    rows = _analytics(report.content["facts"])
    assert len(rows) == 1
    row = rows[0]
    assert row["start_value"] == 38.5 and row["latest_value"] == 40.2
    assert row["count"] == 2 and row["trend"] == "up"
    assert row["min"] == 38.5 and row["max"] == 40.2
    assert abs(row["pct"] - 4.415584415584416) < 1e-9

    assert _format_change(1.7, 4.4) == "+1.7 (+4.4%)"
    sentence = _highlight_sentence(row)
    assert "rose" in sentence and "40.2" in sentence and "38.5" in sentence


# --- API --------------------------------------------------------------------

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


def test_api_report_lifecycle(client, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.reporting import generator as gen

    monkeypatch.setattr(gen, "call_llm", mock_llm)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    test_client, factory = client
    _production_seed(factory)

    resp = test_client.post(
        "/api/v1/reports/generate",
        json={"template_type": "production_summary", "filters": {"entities": ["coal_production"]}},
    )
    assert resp.status_code == 201
    body = resp.json()
    report_id = body["id"]
    assert body["status"] == "draft"
    assert set(body["content"]["sections"]) == {
        "executive_summary",
        "overview",
        "key_figures",
        "trends",
        "observations",
        "sources",
    }

    assert test_client.get(f"/api/v1/reports/{report_id}").status_code == 200
    assert test_client.get("/api/v1/reports/99999").status_code == 404

    assert test_client.post(f"/api/v1/reports/{report_id}/approve").json()["status"] == "reviewed"
    assert test_client.post(f"/api/v1/reports/{report_id}/approve").json()["status"] == "final"
    assert test_client.post(f"/api/v1/reports/{report_id}/approve").status_code == 409

    export = test_client.get(f"/api/v1/reports/{report_id}/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/pdf")
    assert export.content[:5] == b"%PDF-"

    # unknown template is rejected before any LLM work
    bad = test_client.post(
        "/api/v1/reports/generate", json={"template_type": "nope", "filters": {}}
    )
    assert bad.status_code == 400


def test_api_list_reports(client):
    from app.services.reporting import generator as gen

    test_client, factory = client
    original_llm = gen.call_llm
    gen.call_llm = mock_llm
    try:
        report_ids = set()
        for _ in range(2):
            resp = test_client.post(
                "/api/v1/reports/generate",
                json={"template_type": "production_summary", "filters": {}},
            )
            assert resp.status_code == 201
            report_ids.add(resp.json()["id"])
    finally:
        gen.call_llm = original_llm

    resp = test_client.get("/api/v1/reports")
    assert resp.status_code == 200
    rows = resp.json()

    assert {row["id"] for row in rows} >= report_ids
    for row in rows:
        assert set(row) >= {"id", "title", "template_type", "status", "generated_at"}
        assert row["status"] == "draft"


def test_api_list_templates(client):
    test_client, _ = client
    templates = test_client.get("/api/v1/reports/templates")
    assert templates.status_code == 200
    types = {t["template_type"] for t in templates.json()}
    assert types == {"production_summary", "coal_quality_report", "reserve_estimate"}
    assert all(t["sections"] for t in templates.json())