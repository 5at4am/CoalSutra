"""Tabular extraction for `spreadsheet` documents (xlsx/csv via pandas).

Used in the extract stage for spreadsheets. Each sheet becomes one document
page: a searchable text rendering plus the raw cells as a table, so downstream
consumers — RAG retrieval and the report generator alike — see both the text
and the exact values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def extract_spreadsheet_pages(file_path: str) -> list[dict[str, Any]]:
    path = Path(file_path)
    if path.suffix.lower() == ".csv":
        frames = {"Sheet1": pd.read_csv(file_path, dtype=str)}
    else:
        frames = pd.read_excel(file_path, sheet_name=None, dtype=str)

    pages: list[dict[str, Any]] = []
    for page_number, (sheet_name, frame) in enumerate(frames.items(), start=1):
        df = frame.dropna(how="all").fillna("")
        if df.empty:
            continue
        table = [list(df.columns)] + df.values.tolist()
        pages.append(
            {
                "page_number": page_number,
                "sheet_name": sheet_name,
                "text": df.to_string(index=False),
                "tables": [table],
            }
        )
    return pages