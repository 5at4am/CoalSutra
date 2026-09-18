"""Text + table extraction for born-digital PDFs (`digital_pdf`).

Used by the extract stage for documents the router classified as digital:
pdfplumber pulls the native text layer and any embedded tables, producing
`{page_number, text, tables}` records for the normalize stage.
"""

from __future__ import annotations

from typing import Any

import pdfplumber


def extract_pdf_pages(file_path: str) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    with pdfplumber.open(file_path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            raw_tables = page.extract_tables() or []
            tables = [_clean_table(t) for t in raw_tables if t]
            pages.append(
                {"page_number": number, "text": text.strip(), "tables": tables}
            )
    return pages


def _clean_table(table: list[list[Any]]) -> list[list[str]]:
    return [
        [(cell or "").replace("\n", " ").strip() if cell else "" for cell in row]
        for row in table
    ]