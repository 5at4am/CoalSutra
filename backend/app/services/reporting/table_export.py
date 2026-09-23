"""Analyst-friendly exports for a `Report`: CSV, XLSX and DOCX.

Complements the reportlab PDF (`exporter.py`) with spreadsheet/Word formats:

- **CSV** — the key-metrics fact table, one row per fact, ``utf-8-sig`` encoded
  so Excel opens it cleanly (accented names, "MT" units).
- **XLSX** — two sheets: ``Key Facts`` (deduped in-scope facts) and ``Sections``
  (every drafted section with its title, body and cited sources).
- **DOCX** — a Word document: title, meta block, every section in reading order
  followed by its citations, then a fact table.

Everything is deterministic and derived solely from ``report.content`` — no LLM
calls, no invented numbers (the same traceability contract as the PDF).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from app.core.config import settings
from app.models import Report

logger = logging.getLogger(__name__)

FACT_HEADERS = [
    "fact_id",
    "entity",
    "value",
    "unit",
    "date_reference",
    "document_name",
    "page_number",
    "confidence",
]


# --- shared helpers ---------------------------------------------------------


def fact_rows(report: Report) -> list[list]:
    """Deduped in-scope fact rows, mirrors the PDF's Key Metrics table."""
    facts = (report.content or {}).get("facts") or []
    seen: set[tuple] = set()
    rows: list[list] = []
    for fact in facts:
        key = (
            fact.get("entity"),
            fact.get("date_reference"),
            fact.get("value"),
            fact.get("document_name"),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            [
                fact.get("fact_id"),
                fact.get("entity") or "(unknown)",
                fact.get("value"),
                fact.get("unit") or "",
                (fact.get("date_reference") or "")[:10] or "",
                fact.get("document_name") or "",
                fact.get("page_number") or "n/a",
                fact.get("confidence"),
            ]
        )
    return rows


def _output_path(report: Report, suffix: str) -> Path:
    reports_dir = Path(settings.UPLOAD_DIR) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir / f"report_{report.id}.{suffix}"


def _section_order(report: Report) -> list[tuple[str, dict]]:
    sections = (report.content or {}).get("sections") or {}
    ordered: list[tuple[str, dict]] = []
    others: list[tuple[str, dict]] = []
    for key, section in sections.items():
        if key == "executive_summary":
            ordered.append((key, section))
        elif key == "sources":
            continue
        else:
            others.append((key, section))
    ordered.extend(others)
    if "sources" in sections:
        ordered.append(("sources", sections["sources"]))
    return ordered


# --- CSV --------------------------------------------------------------------


def export_report_csv(report: Report, output_path: str | Path | None = None) -> str:
    if output_path is None:
        output_path = _output_path(report, "csv")
    output_path = Path(output_path)

    rows = fact_rows(report)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("report", str(report.id)))
        writer.writerow(("title", str(report.title)))
        writer.writerow(("template", str(report.template_type)))
        writer.writerow(("status", str(report.status.value)))
        writer.writerow(("generated_at", str(report.generated_at)))
        writer.writerow([])
        writer.writerow(FACT_HEADERS)
        writer.writerows(rows)

    logger.info("table_export: wrote report %s CSV to %s", report.id, output_path)
    return str(output_path)


# --- XLSX -------------------------------------------------------------------


def export_report_xlsx(report: Report, output_path: str | Path | None = None) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    if output_path is None:
        output_path = _output_path(report, "xlsx")
    output_path = Path(output_path)

    header_font = Font(bold=True, color="334155")
    header_fill = PatternFill("solid", fgColor="F1F5F9")

    wb = Workbook()

    sheet = wb.active
    sheet.title = "Key Facts"
    sheet.append(FACT_HEADERS)
    for cell in sheet[1]:
        cell.font = header_font
        cell.fill = header_fill
    for row in fact_rows(report):
        sheet.append(row)
    sheet.auto_filter.ref = sheet.dimensions
    sheet.freeze_panes = "A2"
    for index, width in enumerate((10, 24, 14, 10, 14, 32, 10, 12), start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width

    sections_sheet = wb.create_sheet("Sections")
    sections_sheet.append(["section", "title", "body", "sources"])
    for cell in sections_sheet[1]:
        cell.font = header_font
        cell.fill = header_fill
    for _key, section in _section_order(report):
        sources = "".join(
            f"{c.get('document_name')} — page {c.get('page_number') or 'n/a'}\n"
            for c in section.get("citations") or []
        ).rstrip()
        sections_sheet.append(
            [
                str(section.get("title") or ""),
                str(section.get("body") or ""),
                sources,
            ]
        )
    for index, width in enumerate((18, 24, 90, 60), start=1):
        sections_sheet.column_dimensions[get_column_letter(index)].width = width
    for row in sections_sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    meta_sheet = wb.create_sheet("Report")
    meta_sheet.append(["field", "value"])
    for key, value in (
        ("report", report.id),
        ("title", report.title),
        ("template", report.template_type),
        ("status", report.status.value),
        ("generated_at", str(report.generated_at)),
        ("facts", len(fact_rows(report))),
        ("export_path", report.export_path or ""),
    ):
        meta_sheet.append([key, value])

    wb.save(str(output_path))
    logger.info("table_export: wrote report %s XLSX to %s", report.id, output_path)
    return str(output_path)


# --- DOCX -------------------------------------------------------------------


def export_report_docx(report: Report, output_path: str | Path | None = None) -> str:
    from docx import Document
    from docx.shared import Pt

    if output_path is None:
        output_path = _output_path(report, "docx")
    output_path = Path(output_path)

    document = Document()
    styles = document.styles
    styles["Normal"].font.name = "Calibri"
    styles["Normal"].font.size = Pt(10.5)

    document.add_heading("CoalSutra — CMPDI Reporting Assistant", level=0)
    document.add_heading(str(report.title), level=1)
    for label, value in (
        ("Template", report.template_type),
        ("Status", report.status.value),
        ("Generated", str(report.generated_at)),
        ("Report ID", str(report.id)),
    ):
        paragraph = document.add_paragraph()
        run = paragraph.add_run(f"{label}: ")
        run.bold = True
        paragraph.add_run(str(value))

    for key, section in _section_order(report):
        document.add_heading(str(section.get("title") or key), level=2)
        document.add_paragraph(str(section.get("body") or ""))
        citations = section.get("citations") or []
        if citations:
            cite_paragraph = document.add_paragraph()
            cite_run = cite_paragraph.add_run("Sources:")
            cite_run.italic = True
            for citation in citations:
                page = citation.get("page_number") or "n/a"
                document.add_paragraph(
                    f"{citation.get('document_name')} — page {page}",
                    style="List Bullet",
                )

    document.add_heading("Key Facts", level=2)
    rows = fact_rows(report)
    if rows:
        table = document.add_table(rows=1, cols=len(FACT_HEADERS))
        table.style = "Table Grid"
        for index, header in enumerate(FACT_HEADERS):
            table.rows[0].cells[index].text = header
        for row in rows:
            cells = table.add_row().cells
            for index, value in enumerate(row):
                cells[index].text = "" if value is None else str(value)
    else:
        document.add_paragraph("No in-scope facts were available.")

    document.save(str(output_path))
    logger.info("table_export: wrote report %s DOCX to %s", report.id, output_path)
    return str(output_path)


# --- dispatch ---------------------------------------------------------------


EXPORTERS = {
    "csv": export_report_csv,
    "xlsx": export_report_xlsx,
    "docx": export_report_docx,
}


def export_report_table(report: Report, fmt: str, output_path: str | Path | None = None) -> str:
    """Dispatch to the exporter for ``fmt`` (``csv`` | ``xlsx`` | ``docx``)."""
    try:
        exporter = EXPORTERS[fmt]
    except KeyError as exc:
        raise ValueError(f"unsupported export format: {fmt}") from exc
    return exporter(report, output_path)