"""Real OCR end-to-end on a no-text-layer image (RapidOCR, offline).

The rest of the suite mocks the OCR extractor; these tests exercise the actual
RapidOCR (ONNX) engine against a synthetic image with no embedded text layer,
proving the scanned/image ingestion path reads pixels end-to-end.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

pytest.importorskip("rapidocr_onnxruntime")

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.models import Document, DocumentPage  # noqa: E402
from app.models.enums import DocumentStatus, SourceType  # noqa: E402
from app.services.ingestion.extractors.ocr import get_ocr_provider  # noqa: E402
from app.services.ingestion.orchestrator import ingest_document  # noqa: E402


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


def _make_ocr_image(path: Path) -> Path:
    image = Image.new("RGB", (1200, 300), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 64)
    except OSError:
        font = ImageFont.load_default()
    draw.text((60, 90), "Monthly coal production 38.5 MT", fill="black", font=font)
    image.save(path, format="PNG")
    return path


@pytest.mark.slow
def test_rapidocr_reads_tokens_off_no_text_layer_image(tmp_path):
    image_path = _make_ocr_image(tmp_path / "production.png")
    pages = get_ocr_provider("rapidocr").extract(str(image_path))

    assert len(pages) == 1
    assert pages[0]["page_number"] == 1
    text = pages[0]["text"].lower()
    assert "production" in text
    assert "coal" in text
    assert "38.5" in text
    assert "mt" in text


@pytest.mark.slow
def test_image_ingest_end_to_end_processed(tmp_path, monkeypatch, session_factory):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OCR_PROVIDER", "rapidocr")
    image_path = _make_ocr_image(tmp_path / "production.png")

    with session_factory() as session:
        doc = Document(
            filename="production.png",
            source_type=SourceType.scanned_pdf,
            status=DocumentStatus.pending,
            raw_file_path=str(image_path),
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

    ingest_document(doc_id, session_factory=session_factory)

    with session_factory() as session:
        doc = session.get(Document, doc_id)
        pages = session.query(DocumentPage).filter_by(document_id=doc_id).all()

        assert doc.status == DocumentStatus.processed
        assert doc.source_type is not None
        assert pages
        assert any((page.text or "").strip() for page in pages)