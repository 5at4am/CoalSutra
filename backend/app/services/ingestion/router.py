"""Document-type classification — the `route` pipeline stage.

Decides which extraction path a raw upload takes (scanned vs born-digital vs
image vs spreadsheet), mirroring CLAUDE.md's route stage. For PDFs the decision
hinges on whether a text layer exists: near-empty text means the page is a
scanned image, so it must go to OCR rather than native parsing.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from app.models.enums import SourceType

IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
)
SPREADSHEET_EXTENSIONS = frozenset({".csv", ".xlsx", ".xls", ".ods"})
SPREADSHEET_MIME_TYPES = frozenset(
    {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)

MIN_TEXT_CHARS_PER_PAGE = 20


def classify_document(file_path: str, mime_type: str | None = None) -> SourceType:
    suffix = Path(file_path).suffix.lower()
    mime = (mime_type or "").lower()

    if suffix == ".pdf" or mime == "application/pdf":
        return (
            SourceType.scanned_pdf
            if _is_scanned_pdf(file_path)
            else SourceType.digital_pdf
        )
    if suffix in IMAGE_EXTENSIONS or mime.startswith("image/"):
        return SourceType.image
    if suffix in SPREADSHEET_EXTENSIONS or mime in SPREADSHEET_MIME_TYPES:
        return SourceType.spreadsheet

    raise ValueError(f"Unsupported document type for {suffix or mime}")


def _is_scanned_pdf(file_path: str) -> bool:
    try:
        reader = PdfReader(file_path)
        page_count = len(reader.pages)
        total_chars = 0
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            total_chars += len("".join(text.split()))
        if page_count == 0:
            return True
        return total_chars / page_count < MIN_TEXT_CHARS_PER_PAGE
    except Exception:
        return True