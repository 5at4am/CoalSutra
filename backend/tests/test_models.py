from datetime import date

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import (
    ConflictFlag,
    Document,
    ExtractedFact,
    Report,
    SourceType,
    TopicRun,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", _enable_sqlite_fk)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        yield s
    engine.dispose()


def _enable_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def test_fk_relationships_work(session):
    doc = Document(
        filename="bccl_survey_2019.pdf",
        source_type=SourceType.scanned_pdf,
        status="processed",
        raw_file_path="/data/bccl_survey_2019.pdf",
    )
    session.add(doc)
    session.flush()
    assert doc.id is not None

    fact_a = ExtractedFact(
        document_id=doc.id,
        entity="reserve_estimate",
        value="1,240",
        unit="MT",
        date_reference=date(2019, 6, 30),
        page_number=12,
        raw_snippet="Total reserve estimate of 1,240 MT for the Bhubaneshwari block.",
        confidence=0.92,
    )
    fact_b = ExtractedFact(
        document_id=doc.id,
        entity="reserve_estimate",
        value="1,238",
        unit="MT",
        date_reference=date(2019, 6, 30),
        page_number=7,
        raw_snippet="Reserves for Bhubaneshwari pegged at 1,238 MT.",
        confidence=0.71,
    )
    session.add_all([fact_a, fact_b])
    session.flush()
    assert fact_a.id is not None and fact_b.id is not None

    flag = ConflictFlag(
        fact_a_id=fact_a.id,
        fact_b_id=fact_b.id,
        reason="Two documents report a different reserve estimate for the same block/year.",
    )
    report = Report(
        title="Q3 2019 Production Summary - BCCL",
        template_type="production_summary",
        content={
            "section": "Reserves",
            "figures": [
                {"entity": "reserve_estimate", "value": "1,240", "citation": {"page": 12}}
            ],
        },
    )
    topic_run = TopicRun(
        corpus_filter={"subsidiary": "BCCL", "year": 2019},
        topics=[{"label": "Reserves", "keywords": ["reserve", "block"], "doc_count": 4}],
    )
    session.add_all([flag, report, topic_run])
    session.commit()

    assert set(doc.facts) == {fact_a, fact_b}
    assert fact_a.document is doc
    assert fact_b.document is doc
    assert flag.fact_a is fact_a
    assert flag.fact_b is fact_b
    assert flag in fact_a.flags_a
    assert flag in fact_b.flags_b
    assert report.id is not None
    assert topic_run.id is not None


def test_fk_constraint_rejects_orphan_fact(session):
    with pytest.raises(IntegrityError):
        session.add(
            ExtractedFact(
                document_id=9999,
                entity="reserve_estimate",
                value="100",
                raw_snippet="Orphan fact with no document.",
                confidence=0.5,
            )
        )
        session.commit()