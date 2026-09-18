"""Integration tests for the ingest orchestrator (state transitions)."""

from datetime import date

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import ConflictFlag, Document, DocumentPage, ExtractedFact
from app.models.enums import ConflictStatus, DocumentStatus, SourceType
from app.services.ingestion import orchestrator as ing
from app.services.ingestion.orchestrator import ingest_document


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


def _add_document(factory, raw_file_path: str) -> int:
    with factory() as session:
        doc = Document(
            filename="upload.pdf",
            source_type=SourceType.scanned_pdf,
            status=DocumentStatus.pending,
            raw_file_path=raw_file_path,
        )
        session.add(doc)
        session.commit()
        return doc.id


def _assert_status(factory, doc_id, status):
    with factory() as session:
        assert session.get(Document, doc_id).status == status


def test_digital_pdf_processed(session_factory, digital_pdf):
    doc_id = _add_document(session_factory, str(digital_pdf))

    ingest_document(doc_id, session_factory=session_factory)

    with session_factory() as session:
        doc = session.get(Document, doc_id)
        assert doc.status == DocumentStatus.processed
        assert doc.source_type is SourceType.digital_pdf
        assert len(doc.pages) == 1
        assert "reserve" in doc.pages[0].text.lower()

        facts = session.query(ExtractedFact).filter_by(document_id=doc_id).all()
        assert {f.entity for f in facts} == {"coal_reserve", "overburden_ratio"}
        reserve = next(f for f in facts if f.entity == "coal_reserve")
        assert reserve.value == "1240"
        assert reserve.unit == "MT"
        assert reserve.page_number == 1
        assert reserve.confidence > 0.8


def test_csv_processed(session_factory, sample_csv):
    doc_id = _add_document(session_factory, str(sample_csv))

    ingest_document(doc_id, session_factory=session_factory)

    with session_factory() as session:
        doc = session.get(Document, doc_id)
        assert doc.status == DocumentStatus.processed
        assert doc.source_type is SourceType.spreadsheet
        page = session.query(DocumentPage).filter_by(document_id=doc_id).one()
        assert page.page_number == 1
        assert "Bhubaneshwari" in page.text
        assert page.tables is not None

        facts = (
            session.query(ExtractedFact)
            .filter_by(document_id=doc_id)
            .order_by(ExtractedFact.value)
            .all()
        )
        assert [f.value for f in facts] == ["1240", "938"]
        assert all(f.entity == "coal_reserve" and f.unit == "MT" for f in facts)
        assert all(f.date_reference is not None and f.date_reference.year == 2019 for f in facts)


def test_scanned_pdf_processed_via_ocr(session_factory, scanned_pdf, monkeypatch):
    doc_id = _add_document(session_factory, str(scanned_pdf))
    monkeypatch.setattr(
        ing, "ocr_extract", lambda file_path: [{"page_number": 1, "text": "OCR text"}]
    )

    ingest_document(doc_id, session_factory=session_factory)

    with session_factory() as session:
        doc = session.get(Document, doc_id)
        assert doc.status == DocumentStatus.processed
        assert doc.source_type is SourceType.scanned_pdf
        page = session.query(DocumentPage).filter_by(document_id=doc_id).one()
        assert page.text == "OCR text"


def test_status_is_processing_during_extraction(session_factory, digital_pdf, monkeypatch):
    doc_id = _add_document(session_factory, str(digital_pdf))
    seen = {}

    def fake_extract(file_path, source_type):
        with session_factory() as session:
            seen["status"] = session.get(Document, doc_id).status
        return [{"page_number": 1, "text": "x"}]

    monkeypatch.setattr(ing, "_extract_pages", fake_extract)
    ingest_document(doc_id, session_factory=session_factory)

    assert seen["status"] == DocumentStatus.processing


def test_extraction_error_marks_failed(session_factory, digital_pdf, monkeypatch):
    doc_id = _add_document(session_factory, str(digital_pdf))

    def boom(file_path):
        raise RuntimeError("extractor crash")

    monkeypatch.setattr(ing, "extract_pdf_pages", boom)
    ingest_document(doc_id, session_factory=session_factory)

    _assert_status(session_factory, doc_id, DocumentStatus.failed)
    with session_factory() as session:
        assert session.query(DocumentPage).filter_by(document_id=doc_id).count() == 0


def test_validator_flags_conflict_after_ingest(session_factory, digital_pdf, monkeypatch):
    with session_factory() as session:
        other = Document(
            filename="other.pdf",
            source_type=SourceType.digital_pdf,
            status=DocumentStatus.processed,
            raw_file_path="/tmp/other.pdf",
        )
        session.add(other)
        session.flush()
        session.add(
            ExtractedFact(
                document_id=other.id,
                entity="coal_reserve",
                value="1240",
                unit="MT",
                date_reference=date(2019, 1, 1),
                page_number=1,
                raw_snippet="reserve 1240 MT",
                confidence=0.95,
            )
        )
        session.commit()

    new_doc_id = _add_document(session_factory, str(digital_pdf))

    def fake_normalize(document_id, pages):
        return [
            {
                "document_id": document_id,
                "entity": "coal_reserve",
                "value": "938",
                "unit": "MT",
                "date_reference": date(2019, 1, 1),
                "page_number": 1,
                "raw_snippet": "reserve 938 MT fresh",
                "confidence": 0.9,
            }
        ]

    monkeypatch.setattr(ing, "normalize_pages", fake_normalize)
    ingest_document(new_doc_id, session_factory=session_factory)

    with session_factory() as session:
        flags = session.query(ConflictFlag).all()
        assert len(flags) == 1
        assert flags[0].status is ConflictStatus.open
        assert "coal_reserve" in flags[0].reason


def test_missing_document_returns_none(session_factory):
    result = ingest_document(9999, session_factory=session_factory)
    assert result is None