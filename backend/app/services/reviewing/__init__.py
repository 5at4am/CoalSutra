"""Human-in-the-loop review queue: open conflicts + draft reports.

The reviewer resolves one open conflict by declaring which fact is correct
(`fact_a`/`fact_b`/`both`, or `neither` → dismissed) and decides on each draft
report (approve → moves out of draft, or send back with a note). Routes stay
thin: they map model states to HTTP codes, this module owns the decisions.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import ConflictFlag, ExtractedFact, Report
from app.models.enums import ConflictStatus, ReportStatus


class ReviewError(Exception):
    """Review action rejected because of the current model state (→ 409)."""


def build_queue(session: Session) -> dict[str, Any]:
    conflicts = (
        session.query(ConflictFlag)
        .filter(ConflictFlag.status == ConflictStatus.open)
        .order_by(ConflictFlag.id.asc())
        .all()
    )
    drafts = (
        session.query(Report)
        .filter(Report.status == ReportStatus.draft)
        .order_by(Report.id.asc())
        .all()
    )
    return {
        "conflicts": [conflict_item(flag) for flag in conflicts],
        "draft_reports": [report_item(report) for report in drafts],
    }


def resolve_conflict(
    session: Session,
    conflict_id: int,
    decision: str,
    resolved_by: str,
) -> ConflictFlag | None:
    flag = session.get(ConflictFlag, conflict_id)
    if flag is None:
        return None
    if flag.status != ConflictStatus.open:
        raise ReviewError("only open conflicts can be resolved")
    if decision in ("fact_a", "fact_b", "both"):
        flag.status = ConflictStatus.resolved
    elif decision == "neither":
        flag.status = ConflictStatus.dismissed
    else:
        raise ReviewError(f"unknown decision {decision!r}")
    flag.resolution = decision
    flag.resolved_by = resolved_by
    session.flush()
    return flag


def decide_report(
    session: Session,
    report_id: int,
    decision: str,
    comment: str = "",
) -> Report | None:
    report = session.get(Report, report_id)
    if report is None:
        return None
    if report.status != ReportStatus.draft:
        raise ReviewError("only draft reports are pending review")
    if decision == "approve":
        report.status = ReportStatus.reviewed
        if comment:
            report.review_note = comment
    elif decision == "send_back":
        report.review_note = comment
    else:
        raise ReviewError(f"unknown decision {decision!r}")
    session.flush()
    return report


# --- queue item builders ---------------------------------------------------


def conflict_item(flag: ConflictFlag) -> dict[str, Any]:
    return {
        "id": flag.id,
        "status": flag.status.value,
        "reason": flag.reason,
        "resolution": flag.resolution,
        "resolved_by": flag.resolved_by,
        "fact_a": _fact_item(flag.fact_a),
        "fact_b": _fact_item(flag.fact_b),
    }


def _fact_item(fact: ExtractedFact | None) -> dict[str, Any] | None:
    if fact is None:
        return None
    return {
        "fact_id": fact.id,
        "entity": fact.entity,
        "value": fact.value,
        "unit": fact.unit,
        "date_reference": fact.date_reference.isoformat() if fact.date_reference else None,
        "page_number": fact.page_number,
        "document_name": fact.document.filename if fact.document else None,
        "snippet": fact.raw_snippet,
        "confidence": fact.confidence,
    }


def report_item(report: Report) -> dict[str, Any]:
    return {
        "id": report.id,
        "title": report.title,
        "template_type": report.template_type,
        "generated_at": report.generated_at,
        "status": report.status.value,
        "summary": _report_summary(report),
    }


def _report_summary(report: Report, max_chars: int = 200) -> str:
    sections = (report.content or {}).get("sections", {})
    for section in sections.values():
        if section.get("automatic"):
            continue
        body = str(section.get("body", "")).strip()
        if body:
            return body[:max_chars]
    return "No content yet."