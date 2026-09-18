"""API tests for POST /api/v1/documents/upload (upload → background ingest)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models import Document
from app.models.enums import DocumentStatus
from app.services.ingestion import orchestrator as ing
from app.services.ingestion import jobs as jobsvc


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))

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
    ing.SessionLocal = factory
    jobsvc.SessionLocal = factory

    with TestClient(app) as test_client:
        yield test_client, factory

    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def test_csv_upload_is_processed_and_stored(client, sample_csv):
    test_client, factory = client

    with sample_csv.open("rb") as f:
        resp = test_client.post(
            "/api/v1/documents/upload",
            files={"file": ("sample.csv", f, "text/csv")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["source_type"] == "spreadsheet"
    assert body["status"] == "pending"

    uploads_dir = settings.UPLOAD_DIR
    with factory() as session:
        doc = session.get(Document, body["id"])
        assert doc.status is DocumentStatus.processed
        assert len(doc.pages) == 1
        assert doc.raw_file_path.startswith(uploads_dir)


def test_digital_pdf_upload_processed(client, digital_pdf):
    test_client, factory = client

    with digital_pdf.open("rb") as f:
        resp = test_client.post(
            "/api/v1/documents/upload",
            files={"file": ("digital_sample.pdf", f, "application/pdf")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["source_type"] == "digital_pdf"

    with factory() as session:
        doc = session.get(Document, body["id"])
        assert doc.status is DocumentStatus.processed
        assert doc.source_type.value == "digital_pdf"
        assert "reserve" in doc.pages[0].text.lower()


def test_upload_rejects_unsupported_extension(client, tmp_path):
    test_client, factory = client
    notes = tmp_path / "notes.txt"
    notes.write_text("plain notes")

    with notes.open("rb") as f:
        resp = test_client.post(
            "/api/v1/documents/upload",
            files={"file": ("notes.txt", f, "text/plain")},
        )

    assert resp.status_code == 400
    with factory() as session:
        assert session.query(Document).count() == 0