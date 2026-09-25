"""RAG tests: chunking, hybrid retrieval, and the query engine's evidence gate.

The embedding call is mocked with a deterministic keyword-space vectorizer so
`(chunk, query)` cosine similarity is meaningful and controllable. No LLM API
key, no network — the "no evidence found" path must never call the LLM.
"""

import math
import re
import warnings

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models import Document
from app.models.enums import DocumentStatus, SourceType
from app.services.rag import (
    NO_EVIDENCE_MESSAGE,
    chunk_text,
    embed_and_store_chunks,
    retrieve,
)
from app.services.rag.query_engine import QueryAnswer, answer_question

# --- keyword-space fake embedder ------------------------------------------

_KEYWORDS = {"reserve": 0, "ash": 1, "moisture": 2}


def fake_embed(text: str) -> list[float]:
    # Padded to the schema's embedding dimension (the Vector column validates
    # the length even on SQLite); only the keyword slots are non-zero, so
    # cosine similarity behaves exactly like the 3-dim version.
    vec = [0.0] * settings.EMBEDDING_DIM
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        index = _KEYWORDS.get(token)
        if index is not None:
            vec[index] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


# --- fixture --------------------------------------------------------------

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


def _seed_document_with_chunks(factory, filename: str, page_text: str) -> int:
    doc_id = _seed_document(factory, filename)
    with factory() as session:
        embed_and_store_chunks(
            session,
            doc_id,
            [{"page_number": 1, "text": page_text}],
            embed=fake_embed,
        )
        session.commit()
    return doc_id


# --- chunker --------------------------------------------------------------

def test_chunk_text_respects_size_and_overlap():
    text = " ".join(f"word_{i}" for i in range(100))
    tokens = text.split()
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks[0].split()) == 50
    assert len(chunks[1].split()) == 50
    # overlap region: chunk0's trailing 10 tokens == chunk1's leading 10
    assert chunks[0].split()[40:] == chunks[1].split()[:10]
    # advance is chunk_size - overlap = 40 tokens
    assert chunks[1].split()[10:40] == tokens[50:80]


def test_chunk_text_single_short_text():
    assert chunk_text("only a few words", chunk_size=500, overlap=50) == [
        "only a few words"
    ]


# --- embed + store ---------------------------------------------------------

def test_embed_and_store_chunks_persists_chunk_per_page(session_factory):
    doc_id = _seed_document(session_factory, "report.pdf")
    pages = [
        {"page_number": 1, "text": "coal reserve measured 1240 MT today."},
        {"page_number": 2, "text": "ash content typical for this seam."},
    ]
    with session_factory() as session:
        n = embed_and_store_chunks(session, doc_id, pages, embed=fake_embed)
        session.commit()

    assert n == 2
    with session_factory() as session:
        from app.models import DocumentChunk

        chunks = session.query(DocumentChunk).order_by(DocumentChunk.page_number).all()
        assert [c.page_number for c in chunks] == [1, 2]
        assert chunks[0].embedding is not None
        assert len(chunks[0].embedding) == settings.EMBEDDING_DIM


# --- retriever -------------------------------------------------------------

_PAGE_RESERVE = (
    "The opencast block reserve stands at 1240 million tonnes. "
    "Reserve estimate for the block remains 1240 MT as per the approved plan. "
    "The total reserve measured across the lease is 1240 MT."
)
_PAGE_ASH = (
    "Average ash content in this seam is 18 percent. Moisture percentage "
    "varies between 4 and 6. Ash and moisture drive the grade of the coal."
)


def _seed_corpus(factory):
    doc_a = _seed_document_with_chunks(factory, "reserve_report.pdf", _PAGE_RESERVE)
    doc_b = _seed_document_with_chunks(factory, "quality_report.pdf", _PAGE_ASH)
    return doc_a, doc_b


def test_retriever_semantic_query_returns_reserve_chunk(session_factory):
    doc_a, doc_b = _seed_corpus(session_factory)
    with session_factory() as session:
        results = retrieve(
            session,
            "coal reserve production tonnes",
            fake_embed("coal reserve production tonnes"),
            top_k=3,
        )

    assert results  # "reserve" appears exactly in doc A's chunk
    top = results[0]
    assert top["document_id"] == doc_a
    assert top["document_name"] == "reserve_report.pdf"
    assert top["page_number"] == 1
    assert "reserve" in top["text"].lower()
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_retriever_semantic_query_returns_ash_chunk(session_factory):
    doc_a, doc_b = _seed_corpus(session_factory)
    with session_factory() as session:
        results = retrieve(
            session,
            "ash content moisture percentage",
            fake_embed("ash content moisture percentage"),
            top_k=3,
        )

    assert results[0]["document_id"] == doc_b
    assert results[0]["document_name"] == "quality_report.pdf"


def test_retriever_fts_only_votes_through_bm25(session_factory):
    doc_a, doc_b = _seed_corpus(session_factory)
    with session_factory() as session:
        results = retrieve(
            session,
            "approved plan lease",
            fake_embed("approved plan lease"),  # no semantic keywords -> 0 sim
            top_k=2,
        )

    assert results
    # text match alone must still surface the reserve chunk above None
    assert results[0]["document_name"] == "reserve_report.pdf"


# --- query engine ----------------------------------------------------------

def test_query_engine_no_evidence_does_not_call_llm(session_factory):
    _seed_corpus(session_factory)

    def failing_llm(*args, **kwargs):
        raise AssertionError("LLM must not be called when no evidence exists")

    with session_factory() as session:
        result = answer_question(
            session,
            "pizza toppings and flip phones",
            embed=fake_embed,
            llm=failing_llm,
        )

    assert result["answer"] == NO_EVIDENCE_MESSAGE
    assert result["citations"] == []


def test_query_engine_answers_with_citations(session_factory):
    _seed_corpus(session_factory)
    llm_calls = []
    summoned = "1240 MT of coal is reserved as stated in the report."

    def fake_llm(prompt, response_schema):
        llm_calls.append(prompt)
        return QueryAnswer(answer=summoned)

    with session_factory() as session:
        result = answer_question(
            session,
            "how much coal reserve is reported",
            embed=fake_embed,
            llm=fake_llm,
        )

    assert result["answer"] == summoned
    assert len(result["citations"]) >= 1
    assert result["citations"][0]["document_name"] == "reserve_report.pdf"
    assert result["citations"][0]["page_number"] == 1
    assert "reserve" in result["citations"][0]["snippet"].lower()


def test_query_engine_empty_corpus_returns_no_evidence(session_factory):
    with session_factory() as session:
        result = answer_question(
            session,
            "any question at all",
            embed=fake_embed,
            llm=lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("LLM must not be called")
            ),
        )

    assert result["answer"] == NO_EVIDENCE_MESSAGE
    assert result["citations"] == []


# --- API -------------------------------------------------------------------

@pytest.fixture()
def client(session_factory):
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


def test_query_endpoint_answers_with_citations(client, monkeypatch):
    test_client, factory = client
    _seed_corpus(factory)
    import app.services.rag.query_engine as qe

    summoned = "Ash content of the seam is about 18 percent per the report."
    monkeypatch.setattr(qe, "embed_text", fake_embed)
    monkeypatch.setattr(
        qe, "call_llm", lambda prompt, schema: QueryAnswer(answer=summoned)
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resp = test_client.post("/api/v1/query", json={"question": "coal ash"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == summoned
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["document_name"] == "quality_report.pdf"
    assert body["citations"][0]["page_number"] == 1