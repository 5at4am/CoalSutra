"""Topic-model test: a TopicRun is created with well-formed output.

No LLM, no network: the deterministic keyword-label fallback is exercised and
clustering runs over fabricated chunk text via the real numpy TF-IDF + KMeans
path.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Document, DocumentChunk
from app.models.enums import DocumentStatus, SourceType
from app.services.topics.topic_model import run_topic_model


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


def _seed_chunks(factory, filename: str, texts: list[str]) -> int:
    with factory() as session:
        doc = Document(
            filename=filename,
            source_type=SourceType.digital_pdf,
            status=DocumentStatus.processed,
            raw_file_path=f"/tmp/{filename}",
        )
        session.add(doc)
        session.commit()
        for page, text in enumerate(texts, start=1):
            session.add(
                DocumentChunk(
                    document_id=doc.id,
                    page_number=page,
                    text=text,
                    embedding=None,
                )
            )
        session.commit()
        return doc.id


def test_topic_run_created_with_well_formed_output(session_factory):
    _seed_chunks(
        session_factory,
        "reserves.pdf",
        [
            "coal reserve measured 1240 million tonnes at bhubaneswari block",
            "geological reserve estimate for the lease totals 938 million tonnes",
            "mineable reserve extracted during the year reached 45 million tonnes",
        ],
    )
    _seed_chunks(
        session_factory,
        "quality.pdf",
        [
            "ash content in the seam averages 18 percent with high grade coal",
            "moisture percentage varies between 4 and 6 during harvesting",
        ],
    )

    with session_factory() as session:
        run = run_topic_model(session, {"n_topics": 2})

    topics = run.topics
    assert len(topics) == 2
    for topic in topics:
        assert isinstance(topic["label"], str) and topic["label"].strip()
        assert isinstance(topic["top_keywords"], list)
        assert all(isinstance(k, str) and k for k in topic["top_keywords"])
        assert topic["doc_count"] >= 1
        assert topic["chunk_count"] >= 1
    assert sum(t["chunk_count"] for t in topics) == 5

    assert run.id is not None
    assert run.corpus_filter == {"n_topics": 2}
    with session_factory() as session:
        reloaded = session.get(type(run), run.id)
        assert reloaded.topics == topics


def test_topic_run_on_empty_corpus_is_empty(session_factory):
    with session_factory() as session:
        run = run_topic_model(session, {"n_topics": 3})
    assert run.id is not None
    assert run.topics == []