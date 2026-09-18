"""Export a `Report` to a structured, professional PDF (reportlab).

Beyond the drafted narrative sections the PDF adds a brand cover block, an
auto-built Key Metrics table of every in-scope fact, and an **Insight &
Analysis** block computed deterministically from the stored facts (first/latest
value, absolute + percentage change, trend direction, min/max, source count)
plus a simple bar chart when a numeric series has at least two dated points.
Every number rendered here traces back to the source document + page carried by
the fact record — nothing is invented. Page headers/footers carry the brand,
title and page number.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import HRFlowable

from app.core.config import settings
from app.models import Report

logger = logging.getLogger(__name__)

_SPACER = 10
_MAX_TABLE_ROWS = 40
_MAX_CHARTS = 2

_AMBER = colors.HexColor("#B45309")
_AMBER_LIGHT = colors.HexColor("#FEF3C7")
_SLATE = colors.HexColor("#334155")
_SLATE_MUTED = colors.HexColor("#64748B")
_BORDER = colors.HexColor("#CBD5E1")
_HEADER_FILL = colors.HexColor("#F1F5F9")

_STYLE_BY_STATUS = {
    "draft": "#B45309",
    "reviewed": "#1D4ED8",
    "final": "#15803D",
}


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverBrand",
            parent=styles["Normal"],
            fontSize=10,
            textColor=_AMBER,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMeta",
            parent=styles["Normal"],
            fontSize=9,
            textColor=_SLATE_MUTED,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionIntro",
            parent=styles["BodyText"],
            fontSize=9.5,
            textColor=_SLATE_MUTED,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="InsightBullet",
            parent=styles["BodyText"],
            fontSize=9.5,
            leftIndent=10,
            spaceAfter=2,
        )
    )
    return styles


def export_report(report: Report, output_path: str | Path | None = None) -> str:
    """Render ``report.content`` to a PDF and return the file path.

    If ``output_path`` is omitted the PDF is written to
    ``{settings.UPLOAD_DIR}/reports/report_{report.id}.pdf``. The caller is
    responsible for persisting the returned path on the Report row.
    """
    if output_path is None:
        reports_dir = Path(settings.UPLOAD_DIR) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / f"report_{report.id}.pdf"
    else:
        output_path = Path(output_path)

    styles = _styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        title=report.title,
        leftMargin=50,
        rightMargin=50,
        topMargin=66,
        bottomMargin=66,
    )

    sections = (report.content or {}).get("sections", {})
    facts = (report.content or {}).get("facts") or []
    scope = (report.content or {}).get("scope") or {}
    status_text = report.status.value
    status_color = _STYLE_BY_STATUS.get(status_text, "#334155")

    story = _cover(report, scope, len(facts), status_text, status_color, styles)
    story.extend(_key_metrics_block(facts, styles))
    story.extend(_insight_analysis_block(facts, styles))
    story.extend(_sections_block(sections, styles))
    story.extend(_references_block(sections, styles))

    doc.build(story, onFirstPage=_first_page, onLaterPages=_later_page)
    logger.info("exporter: wrote report %s to %s", report.id, output_path)
    return str(output_path)


# --- cover / page furniture ------------------------------------------------


def _cover(
    report: Report,
    scope: dict,
    fact_count: int,
    status_text: str,
    status_color: str,
    styles,
) -> list:
    story = [
        Paragraph(
            "<font color='#B45309'><b>COALSUTRA</b></font> — CMPDI Reporting Assistant",
            styles["CoverBrand"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(escape(report.title), styles["Title"]),
        HRFlowable(width="100%", thickness=1.2, color=_AMBER, spaceBefore=8, spaceAfter=12),
        Paragraph(f"Template: {escape(report.template_type)}", styles["ReportMeta"]),
        Paragraph(
            f"Status: <font color='{status_color}'>{status_text}</font>",
            styles["ReportMeta"],
        ),
        Paragraph(
            f"Generated: {report.generated_at:%Y-%m-%d %H:%M}",
            styles["ReportMeta"],
        ),
    ]
    if scope.get("entities"):
        story.append(
            Paragraph(f"Entities: {escape(', '.join(scope['entities']))}", styles["ReportMeta"])
        )
    if scope.get("date_from") or scope.get("date_to"):
        dates = f"{scope.get('date_from', '...')} to {scope.get('date_to', '...')}"
        story.append(Paragraph(f"Period: {escape(dates)}", styles["ReportMeta"]))
    story.append(
        Paragraph(
            f"Scope: {fact_count} validated fact(s) in scope",
            styles["ReportMeta"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    return story


def _first_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(_AMBER)
    canvas.setLineWidth(1.2)
    canvas.line(50, doc.bottomMargin + 26, A4[0] - 50, doc.bottomMargin + 26)
    canvas.setFillColor(_SLATE_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        50,
        doc.bottomMargin + 12,
        "Every figure is traceable to a source document and page.",
    )
    canvas.restoreState()
    _footer(canvas, doc)


def _later_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(_SLATE_MUTED)
    canvas.setFont("Helvetica", 8)
    title = _shorten(doc.title or "Report", 78)
    canvas.drawString(50, A4[1] - 22 * mm, "CoalSutra")
    canvas.drawRightString(A4[0] - 50, A4[1] - 22 * mm, escape(title))
    canvas.setStrokeColor(_AMBER)
    canvas.setLineWidth(0.8)
    canvas.line(50, A4[1] - 24 * mm, A4[0] - 50, A4[1] - 24 * mm)
    canvas.restoreState()
    _footer(canvas, doc)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(_SLATE_MUTED)
    canvas.setFont("Helvetica", 8)
    template = getattr(doc, "template_type", "")
    canvas.drawString(50, 40, f"CoalSutra — {template}")
    canvas.drawRightString(A4[0] - 50, 40, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --- key metrics table ------------------------------------------------------


def _key_metrics_block(facts: list[dict], styles) -> list:
    story = [
        Paragraph("Key Metrics", styles["Heading1"]),
        Paragraph(
            "Every validated figure in scope, exactly as extracted, with its source.",
            styles["SectionIntro"],
        ),
    ]
    if not facts:
        story.append(Paragraph("No in-scope facts were available.", styles["BodyText"]))
        return story

    rows = [["Entity", "Value", "Unit", "Date", "Source", "Page", "Conf."]]
    for fact in _dedupe_facts(facts)[:_MAX_TABLE_ROWS]:
        page = fact.get("page_number")
        conf = fact.get("confidence")
        rows.append(
            [
                escape(str(fact.get("entity") or "(unknown)")),
                str(fact.get("value") or ""),
                escape(str(fact.get("unit") or "")),
                str((fact.get("date_reference") or "")[:10]),
                escape(str(fact.get("document_name") or "")),
                str(page) if page else "n/a",
                f"{conf * 100:.0f}%" if isinstance(conf, (int, float)) else "",
            ]
        )
    cols = [100, 62, 45, 70, 110, 40, 40]
    table = Table(rows, colWidths=cols, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_FILL),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
                ("TEXTCOLOR", (0, 0), (-1, 0), _SLATE),
                ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _HEADER_FILL]),
                ("ALIGN", (1, 0), (6, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    if len(_dedupe_facts(facts)) > _MAX_TABLE_ROWS:
        story.append(
            Paragraph(
                f"(Showing the first {_MAX_TABLE_ROWS} of "
                f"{len(_dedupe_facts(facts))} facts.)",
                styles["ReportMeta"],
            )
        )
    story.append(Spacer(1, 5 * mm))
    return story


def _dedupe_facts(facts: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
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
        out.append(fact)
    return out


# --- insight & analysis -----------------------------------------------------


def _analytics(facts: list[dict]) -> list[dict]:
    """Per-entity numeric series: first/latest value, change, trend, min/max."""
    by_entity: dict[str, list[tuple[str, float]]] = {}
    for fact in _dedupe_facts(facts):
        value = _to_float(fact.get("value"))
        if value is None:
            continue
        entity = str(fact.get("entity") or "(unknown)")
        by_entity.setdefault(entity, []).append(
            (str(fact.get("date_reference") or "")[:10], value)
        )

    rows: list[dict] = []
    for entity, points in by_entity.items():
        points.sort(key=lambda p: p[0])
        first_date, first_value = points[0]
        latest_date, latest_value = points[-1]
        changed: float | None = None
        if len(points) > 1:
            changed = latest_value - first_value
        pct: float | None = None
        if changed is not None and first_value:
            pct = changed / first_value * 100.0
        trend = "flat"
        if changed and changed > 0:
            trend = "up"
        elif changed and changed < 0:
            trend = "down"
        rows.append(
            {
                "entity": entity,
                "start_date": first_date,
                "start_value": first_value,
                "latest_date": latest_date,
                "latest_value": latest_value,
                "count": len(points),
                "change": changed,
                "pct": pct,
                "trend": trend,
                "min": min(v for _d, v in points),
                "max": max(v for _d, v in points),
                "points": points,
            }
        )
    return sorted(rows, key=lambda r: r["latest_value"], reverse=True)


def _insight_analysis_block(facts: list[dict], styles) -> list:
    story = [
        Paragraph("Insight & Analysis", styles["Heading1"]),
        Paragraph(
            "Computed from the validated facts only; every figure stays traceable "
            "to its source row in Key Metrics.",
            styles["SectionIntro"],
        ),
    ]
    analytics = _analytics(facts)
    if not analytics:
        story.append(
            Paragraph(
                "No numeric series available for trend analysis.",
                styles["BodyText"],
            )
        )
        story.append(Spacer(1, 5 * mm))
        return story

    rows = [["Metric", "Period", "First", "Latest", "Change", "Trend"]]
    for row in analytics:
        period = f"{row['start_date'] or '...'} to {row['latest_date'] or '...'}"
        change = _format_change(row["change"], row["pct"])
        trend = {
            "up": "up",
            "down": "down",
            "flat": "flat",
        }.get(row["trend"], "flat")
        rows.append(
            [
                escape(str(row["entity"])),
                escape(period),
                _format_number(row["start_value"]),
                _format_number(row["latest_value"]),
                change,
                trend,
            ]
        )
    cols = [95, 115, 70, 70, 85, 40]
    table = Table(rows, colWidths=cols, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_FILL),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
                ("TEXTCOLOR", (0, 0), (-1, 0), _SLATE),
                ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _HEADER_FILL]),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Highlights", styles["Heading2"]))
    for row in analytics:
        story.append(Paragraph(f"• {_highlight_sentence(row)}", styles["InsightBullet"]))
    widest = max(analytics, key=lambda r: r["count"])
    story.append(
        Paragraph(
            f"• Widest coverage: {escape(str(widest['entity']))} with {widest['count']} "
            f"dated observation(s).",
            styles["InsightBullet"],
        )
    )
    story.append(Spacer(1, 4 * mm))

    for row in analytics[:_MAX_CHARTS]:
        chart = _bar_chart(row["entity"], row["points"])
        story.append(Paragraph(f"Trend — {escape(str(row['entity']))}", styles["Heading2"]))
        story.append(chart)
        story.append(Spacer(1, 5 * mm))
    return story


def _highlight_sentence(row: dict) -> str:
    entity = escape(str(row["entity"]))
    if row["count"] < 2:
        return (
            f"{entity}: latest reported value {_format_number(row['latest_value'])} "
            f"(period {row['start_date'] or '...'})."
        )
    direction = {"up": "rose", "down": "fell", "flat": "held steady"}.get(
        row["trend"], "held steady"
    )
    change = _format_change(row["change"], row["pct"])
    return (
        f"{entity} {direction} {change} from "
        f"{_format_number(row['start_value'])} ({row['start_date'] or '...'}) to "
        f"{_format_number(row['latest_value'])} ({row['latest_date'] or '...'})."
    )


def _bar_chart(entity: str, points: list[tuple[str, float]]) -> Drawing:
    width, height = 460, 150
    drawing = Drawing(width, height)
    values = [value for _date, value in points]
    baseline = min(values)
    span = max(values) - baseline or 1.0
    plot_bottom = 34
    plot_top = height - 24
    gap, bar_width = 18, 26
    x = 18
    series_max = max(values)
    for date_label, value in points:
        bar_height = (value - baseline) / span * (plot_top - plot_bottom)
        drawing.add(
            Rect(x, plot_bottom, bar_width, bar_height, fillColor=_AMBER, strokeColor=None)
        )
        label = _shorten(date_label or entity, 8)
        text = String(x + bar_width / 2, plot_bottom - 12, label, fontSize=8)
        text.textAnchor = "middle"
        text.fillColor = _SLATE_MUTED
        drawing.add(text)
        value_text = String(x + bar_width / 2, plot_bottom + bar_height + 4, f"{value:g}")
        value_text.textAnchor = "middle"
        value_text.fontSize = 8
        value_text.fillColor = _SLATE
        drawing.add(value_text)
        x += gap + bar_width
    drawing.add(Line(12, plot_bottom, x + 6, plot_bottom, strokeColor=_BORDER, strokeWidth=0.6))
    return drawing


# --- drafted narrative sections + references --------------------------------


def _sections_block(sections: dict, styles) -> list:
    story = []
    for section in sections.values():
        story.append(Paragraph(escape(section.get("title", "Section")), styles["Heading2"]))
        for paragraph in str(section.get("body", "")).splitlines():
            if paragraph.strip():
                story.append(Paragraph(_inline_citations(paragraph), styles["BodyText"]))
                story.append(Spacer(1, _SPACER))
        citations = section.get("citations") or []
        if citations:
            story.append(Paragraph("Cited sources in this section:", styles["BodyText"]))
            for citation in citations:
                document = escape(str(citation["document_name"]))
                page = citation.get("page_number") or "n/a"
                marker = (
                    f"<font size=8> [fact {citation['fact_id']}]</font>"
                    if citation.get("fact_id")
                    else ""
                )
                story.append(
                    Paragraph(f"• {document} — page {page}{marker}", styles["BodyText"])
                )
    return story


def _references_block(sections: dict, styles) -> list:
    story = [Spacer(1, 4 * mm), Paragraph("References / Sources", styles["Heading1"])]
    references = _collect_references(sections)
    if references:
        for document_name, page in references:
            story.append(
                Paragraph(
                    f"{escape(document_name)} — page {page}", styles["BodyText"]
                )
            )
    else:
        story.append(Paragraph("No sources cited.", styles["BodyText"]))
    return story


def _collect_references(sections: dict) -> list[tuple[str, int | None]]:
    seen: set[tuple[str, int | None]] = set()
    ordered: list[tuple[str, int | None]] = []
    for section in sections.values():
        for citation in section.get("citations") or []:
            key = (citation.get("document_name"), citation.get("page_number"))
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered


def _inline_citations(text: str) -> str:
    """Escape text while preserving a lightweight [doc, page] inline style."""
    return escape(text)


# --- numeric helpers --------------------------------------------------------


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).strip().replace(",", "").replace(" ", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _format_number(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.1f}"
    return f"{value:.2f}".rstrip("0").rstrip(".") or "0"


def _format_change(change: float | None, pct: float | None) -> str:
    if change is None:
        return "n/a"
    sign = "+" if change > 0 else ""
    base = f"{sign}{_format_number(change)}"
    if pct is not None:
        base += f" ({sign}{pct:.1f}%)"
    return base