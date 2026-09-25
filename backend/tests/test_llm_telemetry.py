"""LLM telemetry + evaluation endpoints.

The eval-run tests exercise the whole pipeline against a seeded sqlite corpus
(keyword-space fake embeddings so cosine similarity is controllable, no
network). The usage tests seed `LLMUsage` rows directly and read them back
through the summary/calls endpoints.
"""

import math
import re
import zlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models import Document, LLMUsage
from app.models.enums import DocumentStatus, SourceType
from app.services.rag import embed_and_store_chunks

# --- keyword-space fake embedder (same idea as test_rag) -------------------
# The chunk embedding column is Vector(EMBEDDING_DIM), so the fake must emit
# exactly that many dims. Tokens map to stable fixed slots (crc32), making the
# cosine similarity between a question and matching corpus text meaningful.


def fake_embed(text: str) -> list[float]:
    counts: dict[int, float] = {}
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        slot = zlib.crc32(token.encode("utf-8")) % settings.EMBEDDING_DIM
        counts[slot] = counts.get(slot, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    vec = [0.0] * settings.EMBEDDING_DIM
    for slot, count in counts.items():
        vec[slot] = count / norm
    return vec


# --- corpus seeding ---------------------------------------------------------

_BARKHOLA_TEXT = (
    "Measured total geological reserve at Barkhola lease stands at "
    "108.0 million tonnes per approved plan. Proved reserve reaches "
    "52.5 million tonnes against 31 March 2026 cutoff."
)
_SURVEY_TEXT = (
    "Survey report states whole-block reserve 474730 thousand tonnes and "
    "proven reserve 212480 thousand tonnes. Core recovery from boreholes "
    "averages 82.0 percent. Seam thickness equals 4.5 meters. Fe share "
    "recorded in borehole DDH-1 is 22.8 percent."
)


def _seed_corpus(factory) -> None:
    with factory() as session:
        for filename, text in [
            ("Barkhola_Mine_report.pdf", _BARKHOLA_TEXT),
            ("geological_survey_report.pdf", _SURVEY_TEXT),
        ]:
            doc = Document(
                filename=filename,
                source_type=SourceType.digital_pdf,
                status=DocumentStatus.processed,
                raw_file_path=f"/tmp/{filename}",
            )
            session.add(doc)
            session.commit()
            embed_and_store_chunks(
                session, doc.id, [{"page_number": 1, "text": text}], embed=fake_embed
            )
            session.commit()


# --- client fixture ---------------------------------------------------------


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


# --- usage telemetry -------------------------------------------------------


def _seed_usage(factory) -> None:
    with factory() as session:
        session.add_all(
            [
                LLMUsage(
                    endpoint="query",
                    prompt_label="What is the total reserve?",
                    model="gpt-4o-mini",
                    prompt_tokens=250,
                    completion_tokens=40,
                    total_tokens=290,
                    latency_ms=800.0,
                    success=True,
                ),
                LLMUsage(
                    endpoint="query",
                    prompt_label="Seam thickness?",
                    model="gpt-4o-mini",
                    prompt_tokens=200,
                    completion_tokens=30,
                    total_tokens=230,
                    latency_ms=600.0,
                    success=True,
                ),
                LLMUsage(
                    endpoint="report",
                    prompt_label="Generate monthly report",
                    model="gpt-4o-mini",
                    prompt_tokens=1000,
                    completion_tokens=500,
                    total_tokens=1500,
                    latency_ms=3500.0,
                    success=False,
                    error="provider request failed: 429 rate limited",
                ),
            ]
        )
        session.commit()


def test_usage_summary_aggregates_endpoints(client):
    test_client, factory = client
    _seed_usage(factory)

    body = test_client.get("/api/v1/llm/usage/summary").json()

    assert body["total_calls"] == 3
    assert body["total_tokens"] == 290 + 230 + 1500
    assert body["prompt_tokens"] == 250 + 200 + 1000
    assert body["completion_tokens"] == 40 + 30 + 500
    assert body["failed_calls"] == 1
    assert body["success_rate"] == pytest.approx(66.7)
    assert body["avg_latency_ms"] == pytest.approx(1633.3)
    # cost uses the gpt-4o-mini defaults configured in Settings
    assert body["estimated_cost_usd"] > 0

    endpoints = {ep["endpoint"]: ep for ep in body["by_endpoint"]}
    assert set(endpoints) == {"query", "report"}
    assert endpoints["query"]["calls"] == 2
    assert endpoints["query"]["completion_tokens"] == 70
    assert endpoints["report"]["success_rate"] == 0.0
    assert endpoints["report"]["avg_latency_ms"] == pytest.approx(3500.0)


def test_usage_summary_zero_state(client):
    test_client, _ = client

    body = test_client.get("/api/v1/llm/usage/summary").json()

    assert body["total_calls"] == 0
    assert body["total_tokens"] == 0
    assert body["avg_latency_ms"] is None
    assert body["success_rate"] == 0.0
    assert body["by_endpoint"] == []


def test_usage_calls_lists_newest_first(client):
    test_client, factory = client
    _seed_usage(factory)

    body = test_client.get("/api/v1/llm/usage/calls?limit=2").json()

    assert [row["endpoint"] for row in body] == ["report", "query"]
    assert body[0]["total_tokens"] == 1500
    assert body[0]["error"] is not None
    assert body[1]["success"] is True


def test_usage_context_var_attributes_rows(client, monkeypatch):
    test_client, factory = client
    import app.services.usage as usage

    monkeypatch.setattr(usage, "SessionLocal", factory)

    with usage.llm_context("evaluation", "case:barkhola_total_2026"):
        usage.record_usage(model="test-model", prompt_tokens=7, completion_tokens=3)

    with factory() as session:
        row = session.query(LLMUsage).one()
    assert row.endpoint == "evaluation"
    assert row.prompt_label == "case:barkhola_total_2026"
    assert row.total_tokens == 10
    assert row.success is True


# --- evaluation runs --------------------------------------------------------


def test_eval_run_retrieval_persists_and_scores(client, monkeypatch):
    test_client, factory = client
    _seed_corpus(factory)
    import app.services.evaluation as evaluation

    monkeypatch.setattr(evaluation, "embed_text", fake_embed)

    resp = test_client.post("/api/v1/llm/eval/run", json={"with_answers": False})
    assert resp.status_code == 200
    body = resp.json()

    assert body["mode"] == "retrieval"
    assert body["model"] is None
    assert body["questions_evaluated"] == 8
    assert body["per_case"][0]["id"] == "barkhola_total_2026"
    assert isinstance(body["retrieval_recall"], float)
    assert 0.0 <= body["retrieval_recall"] <= 1.0
    assert 0 <= body["passed"] <= 8
    # barkhola total case should retrieve the expected document + value
    barkhola = next(c for c in body["per_case"] if c["id"].startswith("barkhola_total"))
    assert barkhola["ok"] is True
    assert "Barkhola" in " ".join(barkhola["docs_in_retrieved"])
    assert 108.0 in barkhola["values_in_retrieved"]
    # the out-of-corpus case must NOT retrieve anything relevant
    refusal = next(c for c in body["per_case"] if c["id"] == "out_of_corpus")
    assert refusal["ok"] is True
    assert 108.0 not in refusal["values_in_retrieved"]


def test_eval_run_with_answers_scores_answer_track(client, monkeypatch):
    test_client, factory = client
    _seed_corpus(factory)
    import app.services.rag.eval as ev
    import app.services.evaluation as evaluation

    def canned_answer(session, question, top_k=5, embed=None, llm=None):
        case = next(c for c in ev.GOLDEN_CASES if c["question"] == question)
        if case.get("expect_refusal"):
            return {"answer": ev.NO_EVIDENCE_MESSAGE, "citations": []}
        fragment = case["expected_docs"][0]
        doc_name = (
            "Barkhola_Mine_report.pdf"
            if fragment.lower() == "barkhola"
            else "geological_survey_report.pdf"
        )
        return {
            "answer": f"The reported value is {case['expected_values'][0]} MT.",
            "citations": [
                {"document_name": doc_name, "page_number": 1, "snippet": "cited"}
            ],
        }

    monkeypatch.setattr(evaluation, "embed_text", fake_embed)
    monkeypatch.setattr(evaluation, "answer_question", canned_answer)

    resp = test_client.post("/api/v1/llm/eval/run", json={"with_answers": True})
    assert resp.status_code == 200
    body = resp.json()

    assert body["mode"] == "full"
    assert body["answer_accuracy"] >= 0.9  # all value cases answered correctly
    assert body["refusal_passed"] is True
    value_cases = [c for c in body["per_case"] if "answer_ok" in c and not c.get("expect_refusal_is_control")]
    assert value_cases
    assert all(c["answer_ok"] is True for c in value_cases)
    assert "108.0" in next(c["answer"] for c in body["per_case"] if c["id"] == "barkhola_total_2026")


def test_eval_run_survives_answer_failures(client, monkeypatch):
    test_client, factory = client
    _seed_corpus(factory)
    import app.services.evaluation as evaluation

    def broken_answer(session, question, top_k=5, embed=None, llm=None):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(evaluation, "embed_text", fake_embed)
    monkeypatch.setattr(evaluation, "answer_question", broken_answer)

    resp = test_client.post("/api/v1/llm/eval/run", json={"with_answers": True})
    assert resp.status_code == 200
    body = resp.json()

    assert body["mode"] == "full"
    assert all(c["answer_ok"] is False for c in body["per_case"])
    assert all(c["answer_error"] == "provider exploded" for c in body["per_case"])
    assert body["answer_accuracy"] == 0.0
    assert body["refusal_passed"] is False


def test_eval_run_listing_and_detail(client, monkeypatch):
    test_client, factory = client
    _seed_corpus(factory)
    import app.services.evaluation as evaluation

    monkeypatch.setattr(evaluation, "embed_text", fake_embed)
    test_client.post("/api/v1/llm/eval/run", json={})
    test_client.post("/api/v1/llm/eval/run", json={})

    runs = test_client.get("/api/v1/llm/eval/runs").json()
    assert len(runs) == 2
    assert runs[0]["id"] > runs[1]["id"]
    assert runs[0]["questions_evaluated"] == 8

    detail = test_client.get(f"/api/v1/llm/eval/runs/{runs[0]['id']}").json()
    assert detail["id"] == runs[0]["id"]
    assert len(detail["per_case"]) == 8

    missing = test_client.get("/api/v1/llm/eval/runs/999999")
    assert missing.status_code == 404