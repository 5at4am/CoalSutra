"""`ingest_document` orchestrator — the ingest → store backbone.

Loads a Document row, classifies it (route), dispatches to the right extractor
(extract), persists per-page text/tables into `document_pages` (store),
normalizes the pages into `extracted_facts` rows (LLM-first, rule fallback),
then runs cross-source validation and flags any value conflicts instead of
silently overwriting a stored figure. Status is advanced through pending →
processing → processed, or failed on any extraction error, and errors are
logged per document so one bad file never crashes a batch.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Document, DocumentPage, ExtractedFact
from app.models.enums import DocumentStatus, SourceType
from app.services.ingestion.extractors.native_pdf import extract_pdf_pages
from app.services.ingestion.extractors.ocr import extract as ocr_extract
from app.services.ingestion.extractors.spreadsheet import (
    extract_spreadsheet_pages,
)
from app.services.ingestion.router import classify_document
from app.services.normalization.normalizer import (
    facts_from_pages as normalize_pages,
)
from app.services.normalization.validator import flag_conflicts
from app.services.rag.embedder import embed_and_store_chunks

logger = logging.getLogger(__name__)


def ingest_document(
    document_id: int,
    session_factory: Callable[[], Session] | None = None,
) -> Document | None:
    factory = session_factory or SessionLocal
    session = factory()
    document = session.get(Document, document_id)
    try:
        if document is None:
            logger.error("ingest_document: document %s not found", document_id)
            return None

        document.status = DocumentStatus.processing
        session.commit()

        source_type = classify_document(document.raw_file_path)
        document.source_type = source_type

        pages = _extract_pages(document.raw_file_path, source_type)
        for page in pages:
            session.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=page["page_number"],
                    text=page.get("text", ""),
                    tables=page.get("tables"),
                )
            )
        for fact in normalize_pages(document.id, pages):
            session.add(ExtractedFact(**fact))
        session.flush()
        try:
            flagged = flag_conflicts(session, document.id)
            if flagged:
                logger.info(
                    "validator: flagged %d conflict(s) for document %s",
                    len(flagged),
                    document.id,
                )
        except Exception:
            logger.exception(
                "validator: conflict detection failed for document %s (non-fatal)",
                document.id,
            )
        try:
            n_chunks = embed_and_store_chunks(session, document.id, pages)
            logger.info(
                "embedder: stored %d chunk(s) for document %s",
                n_chunks,
                document.id,
            )
        except Exception:
            logger.exception(
                "embedder: chunking/embedding failed for document %s (non-fatal)",
                document.id,
            )
        document.status = DocumentStatus.processed
        session.commit()
        logger.info(
            "ingest_document: document %s processed (%d pages)", document_id, len(pages)
        )
    except Exception:
        logger.exception("ingest_document: document %s failed", document_id)
        if document is not None:
            document.status = DocumentStatus.failed
            session.commit()
    finally:
        session.close()
    return document


def _extract_pages(
    file_path: str, source_type: SourceType
) -> list[dict]:
    if source_type == SourceType.digital_pdf:
        return extract_pdf_pages(file_path)
    if source_type == SourceType.spreadsheet:
        return extract_spreadsheet_pages(file_path)
    return ocr_extract(file_path)