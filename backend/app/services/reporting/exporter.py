"""Export a `Report` to a structured, professional PDF (reportlab).

Layout:

1. **Cover page** — centred CoalSutra brand, report title, meta grid
   (template / status / generated / scope), traceability tagline.
2. **Contents** — numbered sections with page numbers (built via a two-pass
   TableOfContents).
3. **1. Executive Summary** — the template's executive summary draft.
4. **2. Key Metrics** — every in-scope fact in a zebra table with its source.
5. **3. Insight & Analysis** — DETERMINISTIC analytics (first/latest value,
   absolute + % change, trend, min/max, biggest single-period move) plus native
   vector bar charts, so nothing in this block is ever invented.
6. **n. narrative template sections** — LLM-drafted prose, still cited.
7. **last. References / Sources** — every cited document + page.

Page headers carry the brand + report title; footers carry the page number.
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
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.platypus.tableofcontents import TableOfContents

from app.core.config import settings
from app.models import Report

logger = logging.getLogger(__name__)

_SPACER = 10
_MAX_TABLE_ROWS = 40
_MAX_CHARTS = 2

_AMBER = colors.HexColor("#B45309")
_SLATE = colors.HexColor("#334155")
_SLATE_MUTED = colors.HexColor("#64748B")
_BORDER = colors.HexColor("#CBD5E1")
_GRID = colors.HexColor("#E2E8F0")
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
            fontName="Helvetica-Bold",
            fontSize=15,
            textColor=_AMBER,
            alignment=1,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverTagline",
            parent=styles["Normal"],
            fontSize=9,
            textColor=_SLATE_MUTED,
            alignment=1,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontSize=19,
            textColor=_SLATE,
            alignment=1,
            spaceBefore=10,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMeta",
            parent=styles["Normal"],
            fontSize=9,
            textColor=_SLATE_MUTED,
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
            name="SectionHeading",
            parent=styles["Heading1"],
            fontSize=13,
            textColor=_SLATE,
            spaceBefore=14,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TOCHeading",
            parent=styles["SectionHeading"],
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubHeading",
            parent=styles["Heading2"],
            fontSize=11,
            textColor=_SLATE,
            spaceBefore=10,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TocEntry0",
            parent=styles["Normal"],
            fontSize=10.5,
            leading=16,
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


# --- document template (two-pass TOC) ---------------------------------------


class _ReportDoc(BaseDocTemplate):
    def __init__(self, filename, report_title: str, report_id: int | None, **kw):
        super().__init__(filename, **kw)
        self.report_title = report_title
        self.report_id = report_id
        frame = Frame(50, 58, A4[0] - 100, A4[1] - 138, id="body")
        self.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[frame], onPage=self._cover_page),
                PageTemplate(id="content", frames=[frame], onPage=self._content_page),
            ]
        )

    def afterFlowable(self, flowable):
        if (
            isinstance(flowable, Paragraph)
            and getattr(flowable.style, "name", "") == "SectionHeading"
        ):
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))

    def _cover_page(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(_AMBER)
        canvas.setLineWidth(1.0)
        canvas.line(50, 64, A4[0] - 50, 64)
        canvas.setFillColor(_SLATE_MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(
            A4[0] / 2, 48, "Every figure is traceable to a source document and page."
        )
        canvas.restoreState()

    def _content_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(_SLATE_MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(50, A4[1] - 44, "CoalSutra — CMPDI Reporting Assistant")
        canvas.drawRightString(A4[0] - 50, A4[1] - 44, _shorten(self.report_title, 70))
        canvas.setStrokeColor(_AMBER)
        canvas.setLineWidth(0.8)
        canvas.line(50, A4[1] - 50, A4[0] - 50, A4[1] - 50)
        canvas.setFont("Helvetica", 8)
        ref = f"report {self.report_id}" if self.report_id else ""
        canvas.drawString(50, 44, f"CoalSutra · {ref}" if ref else "CoalSutra")
        canvas.drawRightString(A4[0] - 50, 44, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()


# --- export ----------------------------------------------------------------


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
    doc = _ReportDoc(
        str(output_path),
        pagesize=A4,
        title=report.title,
        leftMargin=50,
        rightMargin=50,
        topMargin=80,
        bottomMargin=58,
        report_title=report.title,
        report_id=report.id,
    )

    sections = (report.content or {}).get("sections", {})
    facts = (report.content or {}).get("facts") or []
    scope = (report.content or {}).get("scope") or {}
    status_text = report.status.value
    status_color = _STYLE_BY_STATUS.get(status_text, "#334155")

    story = _cover(report, scope, facts, status_text, status_color, styles)
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())
    story.append(Paragraph("Contents", styles["TOCHeading"]))
    toc = TableOfContents()
    toc.levelStyles = [styles["TocEntry0"]]
    story.append(toc)
    story.append(Spacer(1, 6 * mm))

    counter = _Counter()
    exec_section = sections.get("executive_summary")
    if exec_section:
        _push_section(
            story, styles, counter.next(), "Executive Summary",
            _section_flow(exec_section, styles, citations=False),
        )
    _push_section(
        story, styles, counter.next(), "Key Metrics", _key_metrics_flow(facts, styles)
    )
    _push_section(
        story, styles, counter.next(), "Insight & Analysis",
        _insight_flow(facts, styles),
    )
    for key, section in sections.items():
        if key in {"executive_summary", "sources"}:
            continue
        _push_section(
            story, styles, counter.next(), section.get("title", key),
            _section_flow(section, styles),
        )
    _push_section(
        story, styles, counter.next(), "References / Sources",
        _references_flow(sections, styles),
    )

    doc.multiBuild(story)
    logger.info("exporter: wrote report %s to %s", report.id, output_path)
    return str(output_path)


class _Counter:
    def __init__(self) -> None:
        self.value = 0

    def next(self) -> int:
        self.value += 1
        return self.value


def _push_section(story: list, styles, number: int, title: str, flow: list) -> None:
    heading = Paragraph(f"{number}. {escape(title)}", styles["SectionHeading"])
    if flow and isinstance(flow[0], Paragraph):
        story.append(KeepTogether([heading, flow[0]]))
        story.extend(flow[1:])
    else:
        story.append(heading)
        story.extend(flow)
    story.append(Spacer(1, 5 * mm))


# --- cover ------------------------------------------------------------------


def _cover(
    report: Report,
    scope: dict,
    facts: list[dict],
    status_text: str,
    status_color: str,
    styles,
) -> list:
    story = [
        Spacer(1, 30 * mm),
        Paragraph("COALSUTRA", styles["CoverBrand"]),
        Paragraph("CMPDI Reporting Assistant", styles["CoverTagline"]),
        Paragraph(escape(report.title), styles["CoverTitle"]),
        HRFlowable(width="45%", hAlign="CENTER", thickness=1.2, color=_AMBER,
                   spaceBefore=6, spaceAfter=16),
    ]

    sources = sorted({f["document_name"] for f in facts if f.get("document_name")})
    period_bits = []
    if scope.get("date_from"):
        period_bits.append(scope["date_from"])
    if scope.get("date_to"):
        period_bits.append("to " + scope["date_to"])
    period = " ".join(period_bits) if period_bits else "full corpus"

    meta = [
        ["Template", report.template_type],
        ["Status", f"<font color='{status_color}'><b>{status_text}</b></font>"],
        ["Generated", f"{report.generated_at:%Y-%m-%d %H:%M}"],
        ["Entities", (", ".join(scope.get("entities", [])) or "all extracted")],
        ["Period", period],
        ["Facts in scope", str(len(facts))],
        ["Sources", str(len(sources))],
    ]
    table = Table(meta, colWidths=[120, 300], hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                ("FONT", (1, 0), (1, -1), "Helvetica", 9.5),
                ("TEXTCOLOR", (0, 0), (0, -1), _SLATE_MUTED),
                ("TEXTCOLOR", (1, 0), (1, -1), _SLATE),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 16 * mm))
    return story


# --- key metrics ------------------------------------------------------------


def _key_metrics_flow(facts: list[dict], styles) -> list:
    flow = [
        Paragraph(
            "Every validated figure in scope, exactly as extracted, with its source.",
            styles["SectionIntro"],
        )
    ]
    if not facts:
        flow.append(Paragraph("No in-scope facts were available.", styles["BodyText"]))
        return flow

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
    table = Table(rows, colWidths=[100, 62, 45, 70, 110, 40, 40], repeatRows=1)
    table.setStyle(_table_style())
    flow.append(table)
    if len(_dedupe_facts(facts)) > _MAX_TABLE_ROWS:
        flow.append(
            Paragraph(
                f"(Showing the first {_MAX_TABLE_ROWS} of "
                f"{len(_dedupe_facts(facts))} facts.)",
                styles["ReportMeta"],
            )
        )
    return flow


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_FILL),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
            ("TEXTCOLOR", (0, 0), (-1, 0), _SLATE),
            ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _HEADER_FILL]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )


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
        largest_move = None
        if len(points) > 2:
            moves = []
            for (from_date, from_value), (to_date, to_value) in zip(points, points[1:]):
                delta = to_value - from_value
                moves.append((abs(delta), {
                    "from_date": from_date,
                    "to_date": to_date,
                    "delta": delta,
                    "pct": delta / from_value * 100.0 if from_value else None,
                }))
            if moves:
                largest_move = max(moves, key=lambda m: m[0])[1]
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
                "largest_move": largest_move,
                "points": points,
            }
        )
    return sorted(rows, key=lambda r: r["latest_value"], reverse=True)


def _insight_flow(facts: list[dict], styles) -> list:
    flow = [
        Paragraph(
            "Computed from the validated facts only; every figure stays traceable "
            "to its source row in Key Metrics.",
            styles["SectionIntro"],
        )
    ]
    analytics = _analytics(facts)
    if not analytics:
        flow.append(
            Paragraph(
                "No numeric series available for trend analysis.",
                styles["BodyText"],
            )
        )
        return flow

    rows = [["Metric", "Period", "First", "Latest", "Change", "Trend"]]
    for row in analytics:
        period = f"{row['start_date'] or '...'} to {row['latest_date'] or '...'}"
        rows.append(
            [
                escape(str(row["entity"])),
                escape(period),
                _format_number(row["start_value"]),
                _format_number(row["latest_value"]),
                _format_change(row["change"], row["pct"]),
                row["trend"],
            ]
        )
    table = Table(rows, colWidths=[95, 115, 70, 70, 85, 40], repeatRows=1)
    table.setStyle(_table_style())
    flow.append(table)
    flow.append(Spacer(1, 3 * mm))

    flow.append(Paragraph("Highlights", styles["SubHeading"]))
    for row in analytics:
        flow.append(Paragraph(f"• {_highlight_sentence(row)}", styles["InsightBullet"]))
    widest = max(analytics, key=lambda r: r["count"])
    flow.append(
        Paragraph(
            f"• Widest coverage: {escape(str(widest['entity']))} with {widest['count']} "
            f"dated observation(s).",
            styles["InsightBullet"],
        )
    )
    flow.append(Spacer(1, 3 * mm))

    for row in analytics[:_MAX_CHARTS]:
        flow.append(
            Paragraph(f"Trend — {escape(str(row['entity']))}", styles["SubHeading"])
        )
        flow.append(_bar_chart(row["entity"], row["points"]))
        flow.append(Spacer(1, 3 * mm))
    return flow


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
    sentence = (
        f"{entity} {direction} {change} from "
        f"{_format_number(row['start_value'])} ({row['start_date'] or '...'}) to "
        f"{_format_number(row['latest_value'])} ({row['latest_date'] or '...'})."
    )
    largest = row.get("largest_move")
    if largest:
        delta = _format_change(largest["delta"], largest["pct"])
        sentence += (
            f" Largest single-period move: {delta} between "
            f"{largest['from_date'] or '...'} and {largest['to_date'] or '...'}."
        )
    return sentence


def _bar_chart(entity: str, points: list[tuple[str, float]]) -> Drawing:
    width, height = 460, 150
    drawing = Drawing(width, height)
    values = [value for _date, value in points]
    baseline = min(values)
    span = max(values) - baseline or 1.0
    plot_bottom = 34
    plot_top = height - 26
    gap, bar_width = 18, 26
    plot_left = 18
    plot_right = plot_left + len(points) * (gap + bar_width) - gap

    for i in range(1, 4):
        value = baseline + span * i / 3
        y = plot_bottom + (value - baseline) / span * (plot_top - plot_bottom)
        drawing.add(Line(plot_left, y, plot_right, y, strokeColor=_GRID, strokeWidth=0.5))
        label = String(plot_right + 4, y - 3, f"{value:g}", fontSize=7)
        label.fillColor = _SLATE_MUTED
        drawing.add(label)

    x = plot_left
    for date_label, value in points:
        bar_height = (value - baseline) / span * (plot_top - plot_bottom)
        drawing.add(
            Rect(x, plot_bottom, bar_width, bar_height, fillColor=_AMBER, strokeColor=None)
        )
        label = _shorten((date_label or entity)[:7] or entity, 9)
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
    drawing.add(Line(plot_left, plot_bottom, plot_right, plot_bottom,
                     strokeColor=_SLATE_MUTED, strokeWidth=0.8))
    return drawing


# --- drafted narrative sections + references --------------------------------


def _section_flow(section: dict, styles, citations: bool = True) -> list:
    flow: list = []
    for paragraph in str(section.get("body", "")).splitlines():
        if paragraph.strip():
            flow.append(Paragraph(_inline_citations(paragraph), styles["BodyText"]))
            flow.append(Spacer(1, _SPACER))
    if citations:
        cited = section.get("citations") or []
        if cited:
            flow.append(Paragraph("Cited sources in this section:", styles["BodyText"]))
            for citation in cited:
                document = escape(str(citation["document_name"]))
                page = citation.get("page_number") or "n/a"
                marker = (
                    f"<font size=8> [fact {citation['fact_id']}]</font>"
                    if citation.get("fact_id")
                    else ""
                )
                flow.append(
                    Paragraph(f"• {document} — page {page}{marker}", styles["BodyText"])
                )
    return flow


def _references_flow(sections: dict, styles) -> list:
    flow: list = []
    references = _collect_references(sections)
    if references:
        for document_name, page in references:
            flow.append(
                Paragraph(f"{escape(document_name)} — page {page}", styles["BodyText"])
            )
    else:
        flow.append(Paragraph("No sources cited.", styles["BodyText"]))
    return flow


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


# --- numeric / text helpers -------------------------------------------------


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


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."