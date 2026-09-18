"""Extraction backends for the `extract` pipeline stage.

Every extractor exposes the same result contract so the orchestrator can treat
document types uniformly: a list of page dicts with `page_number`, `text`, and
optionally `tables`. Swapping in a new OCR provider (e.g. a Vision-LLM) only
requires implementing that contract in `ocr.py`.
"""

from app.services.ingestion.extractors.native_pdf import extract_pdf_pages
from app.services.ingestion.extractors.ocr import extract as ocr_extract
from app.services.ingestion.extractors.ocr import get_ocr_provider
from app.services.ingestion.extractors.spreadsheet import extract_spreadsheet_pages

__all__ = [
    "extract_pdf_pages",
    "extract_spreadsheet_pages",
    "get_ocr_provider",
    "ocr_extract",
]