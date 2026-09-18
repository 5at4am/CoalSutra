"""Report lifecycle endpoints: generate, read, approve, export.

Thin handlers over `app/services/reporting/`. Generation produces a draft;
`approve` advances draft → reviewed → final (one step per call); `export`
renders the current content to PDF via reportlab and records the path.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Report
from app.models.enums import ReportStatus
from app.schemas import ReportGenerate, ReportRead
from app.services.reporting.exporter import export_report
from app.services.reporting.generator import generate_report
from app.services.reporting.lint import lint_sections
from app.services.reporting.templates import get_template, list_templates as _list_templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

_NEXT_STATUS = {
    ReportStatus.draft: ReportStatus.reviewed,
    ReportStatus.reviewed: ReportStatus.final,
}


@router.get("/templates")
def list_templates() -> list[dict]:
    return _list_templates()


@router.get("", response_model=list[ReportRead])
def list_reports(db: Session = Depends(get_db)) -> list[Report]:
    return (
        db.query(Report).order_by(Report.generated_at.desc()).all()
    )


@router.post("/generate", response_model=ReportRead, status_code=201)
def generate(req: ReportGenerate, db: Session = Depends(get_db)) -> Report:
    try:
        get_template(req.template_type)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    report = generate_report(
        db, req.template_type, filters=req.filters, title=req.title
    )
    logger.info("api/reports/generate: draft report %s created", report.id)
    return report


@router.get("/{report_id}", response_model=ReportRead)
def get_report(report_id: int, db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report


@router.get("/{report_id}/lint")
def lint_report(report_id: int, db: Session = Depends(get_db)) -> dict:
    """Facts-check lint: every figure in drafted sections must be backed and cited."""
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    content = report.content or {}
    return lint_sections(
        content.get("sections") or {},
        content.get("facts") or [],
    )


@router.post("/{report_id}/approve", response_model=ReportRead)
def approve_report(report_id: int, db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    previous = report.status
    next_status = _NEXT_STATUS.get(previous)
    if next_status is None:
        raise HTTPException(status_code=409, detail="report is already final")
    report.status = next_status
    db.commit()
    db.refresh(report)
    logger.info(
        "api/reports/approve: report %s %s -> %s",
        report_id,
        previous.value,
        next_status.value,
    )
    return report


@router.get("/{report_id}/export")
def export(report_id: int, db: Session = Depends(get_db)) -> FileResponse:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    try:
        path = export_report(report)
    except Exception as exc:
        logger.exception("api/reports/export: failed for report %s", report_id)
        raise HTTPException(status_code=500, detail=f"pdf export failed: {exc}") from exc

    if report.export_path != path:
        report.export_path = path
        db.commit()
    filename = f"report_{report.id}.pdf"
    return FileResponse(
        path, media_type="application/pdf", filename=filename
    )