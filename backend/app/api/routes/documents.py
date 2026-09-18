"""Document ingestion endpoints (upload → background ingest).

Thin handlers: save the uploaded file, create the Document row, then hand the
rest to `ingest_document` as a FastAPI BackgroundTask (swap point for a real
queue later). The `source_type` written at upload time is provisional — the
router re-classifies inside the orchestrator, which is where scanned vs digital
PDFs are truly decided.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Document
from app.schemas import DocumentRead, DocumentSummary
from app.services.ingestion.orchestrator import ingest_document
from app.services.ingestion.router import classify_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentSummary], summary="List ingested documents")
def list_documents(db: Session = Depends(get_db)) -> list[DocumentSummary]:
    docs = db.query(Document).order_by(Document.id.desc()).all()
    return [
        DocumentSummary(
            id=doc.id,
            filename=doc.filename,
            source_type=doc.source_type,
            upload_date=doc.upload_date,
            status=doc.status,
            raw_file_path=doc.raw_file_path,
            fact_count=len(doc.facts),
        )
        for doc in docs
    ]


@router.post("/upload", response_model=DocumentRead, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
) -> Document:
    if background_tasks is None:
        background_tasks = BackgroundTasks()
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload").suffix
    stored_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    stored_path.write_bytes(await file.read())

    try:
        source_type = classify_document(str(stored_path), file.content_type)
    except ValueError as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    document = Document(
        filename=file.filename or stored_path.name,
        source_type=source_type,
        status="pending",
        raw_file_path=str(stored_path),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(ingest_document, document.id)
    logger.info("upload /api/v1/documents/upload: queued document %s", document.id)
    return document