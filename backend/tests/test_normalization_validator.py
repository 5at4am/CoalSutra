"""Validator conflict-detection tests using fabricated ExtractedFact rows.

No LLM, no network — `flag_conflicts` runs pure Python over rows we insert
directly, matching the hard requirement that the comparison logic is testable
in isolation.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import ConflictFlag, Document, ExtractedFact
from app.models.enums import ConflictStatus, DocumentStatus, SourceType
from app.services.normalization.validator import flag_conflicts


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


def _add_document(factory, source_type=SourceType.digital_pdf) -> int:
    with factory() as session:
        doc = Document(
            filename=f"doc_{source_type.value}.pdf",
            source_type=source_type,
            status=DocumentStatus.processed,
            raw_file_path="/tmp/fake.pdf",
        )
        session.add(doc)
        session.commit()
        return doc.id


def _add_fact(
    factory,
    document_id: int,
    entity: str = "coal_reserve",
    value: str = "1240",
    unit: str = "MT",
    date_reference: date | None = date(2019, 1, 1),
    raw_snippet: str | None = None,
) -> int:
    with factory() as session:
        fact = ExtractedFact(
            document_id=document_id,
            entity=entity,
            value=value,
            unit=unit,
            date_reference=date_reference,
            page_number=1,
            raw_snippet=raw_snippet or f"{entity} {value}",
            confidence=0.95,
        )
        session.add(fact)
        session.commit()
        return fact.id


def _fact_id(factory, document_id: int, value: str) -> int:
    with factory() as session:
        return (
            session.query(ExtractedFact.id)
            .filter_by(document_id=document_id, value=value)
            .scalar()
        )


def _flags(factory) -> list[ConflictFlag]:
    with factory() as session:
        return session.query(ConflictFlag).all()


def test_conflict_created_for_different_documents(session_factory):
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    fact_a_id = _add_fact(session_factory, doc_a, value="1240")
    fact_b_id = _add_fact(session_factory, doc_b, value="938")

    with session_factory() as session:
        flags = flag_conflicts(session, document_id=doc_b)

    assert len(flags) == 1
    flag = flags[0]
    assert flag.status is ConflictStatus.open
    assert {flag.fact_a_id, flag.fact_b_id} == {fact_a_id, fact_b_id}
    assert "coal_reserve" in flag.reason
    assert "1240" in flag.reason and "938" in flag.reason


def test_no_conflict_when_same_value(session_factory):
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    _add_fact(session_factory, doc_a, value="1240")
    _add_fact(session_factory, doc_b, value="1,240")

    with session_factory() as session:
        flags = flag_conflicts(session, document_id=doc_b)

    assert flags == []


def test_no_conflict_when_different_year(session_factory):
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    _add_fact(session_factory, doc_a, value="1240", date_reference=date(2019, 1, 1))
    _add_fact(session_factory, doc_b, value="938", date_reference=date(2020, 1, 1))

    with session_factory() as session:
        flags = flag_conflicts(session, document_id=doc_b)

    assert flags == []


def test_no_conflict_within_same_document(session_factory):
    doc_a = _add_document(session_factory)
    _add_fact(session_factory, doc_a, value="1240")
    _add_fact(session_factory, doc_a, value="938")

    with session_factory() as session:
        flags = flag_conflicts(session, document_id=doc_a)

    assert flags == []


def test_no_conflict_when_different_entity(session_factory):
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    _add_fact(session_factory, doc_a, entity="coal_reserve", value="1240")
    _add_fact(session_factory, doc_b, entity="ash_content", value="938")

    with session_factory() as session:
        flags = flag_conflicts(session, document_id=doc_b)

    assert flags == []


def test_no_conflict_when_date_reference_missing(session_factory):
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    _add_fact(session_factory, doc_a, value="1240", date_reference=None)
    _add_fact(session_factory, doc_b, value="938", date_reference=None)

    with session_factory() as session:
        flags = flag_conflicts(session, document_id=doc_b)

    assert flags == []


def test_conflict_shared_year_with_different_months(session_factory):
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    _add_fact(session_factory, doc_a, value="1240", date_reference=date(2019, 3, 1))
    _add_fact(session_factory, doc_b, value="938", date_reference=date(2019, 9, 30))

    with session_factory() as session:
        flags = flag_conflicts(session, document_id=doc_b)

    assert len(flags) == 1
    assert flags[0].status is ConflictStatus.open


def test_idempotent_does_not_reflag(session_factory):
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    _add_fact(session_factory, doc_a, value="1240")
    _add_fact(session_factory, doc_b, value="938")

    with session_factory() as session:
        first = flag_conflicts(session, document_id=doc_b)
        session.commit()
        second = flag_conflicts(session, document_id=doc_b)

    assert len(first) == 1
    assert second == []
    assert len(_flags(session_factory)) == 1


def test_multiple_conflicting_documents_flag_all(session_factory):
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    doc_c = _add_document(session_factory)
    _add_fact(session_factory, doc_a, value="1240")
    _add_fact(session_factory, doc_b, value="938")
    _add_fact(session_factory, doc_c, value="1200")

    with session_factory() as session:
        flags = flag_conflicts(session, document_id=doc_b)

    assert len(flags) == 2


def test_value_pairs_are_ordered_by_id(session_factory):
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    fact_a_id = _add_fact(session_factory, doc_a, value="1240")
    fact_b_id = _add_fact(session_factory, doc_b, value="938")

    with session_factory() as session:
        flag = flag_conflicts(session, document_id=doc_b)[0]

    assert flag.fact_a_id == min(fact_a_id, fact_b_id)
    assert flag.fact_b_id == max(fact_a_id, fact_b_id)


def test_conflict_found_when_each_doc_lists_multiple_values(session_factory):
    """Regression: two docs both carry 1240 + 938; the 938 collision must flag."""
    doc_a = _add_document(session_factory)
    doc_b = _add_document(session_factory)
    _add_fact(session_factory, doc_a, value="1240", raw_snippet="Bhubaneshwari reserve 1240 MT")
    _add_fact(session_factory, doc_a, value="938", raw_snippet="Kusunda reserve 938 MT")
    _add_fact(session_factory, doc_b, value="1240", raw_snippet="Bhubaneshwari reserve 1240 MT")
    _add_fact(session_factory, doc_b, value="938", raw_snippet="Kusunda reserve 938 MT")

    with session_factory() as session:
        flags = flag_conflicts(session, document_id=doc_b)

    assert len(flags) == 1
    assert {flags[0].fact_a_id, flags[0].fact_b_id} == {
        _fact_id(session_factory, value="1240", document_id=doc_a),
        _fact_id(session_factory, value="938", document_id=doc_b),
    }