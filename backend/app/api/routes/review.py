"""Human-in-the-loop review endpoints over one screen.

Thin handlers over `app/services/reviewing/`: the queue joins open conflict
flags (with both facts' values + sources) and draft reports (title + summary)
so a reviewer can decide without opening another view. Resolution records which
fact is treated as correct; report decisions approve a draft or send it back
with a comment.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    ConflictFlagRead,
    ConflictResolveRequest,
    ReportDecisionRequest,
    ReportRead,
    ReviewQueueRead,
)
from app.services.reviewing import (
    ReviewError,
    build_queue,
    decide_report,
    resolve_conflict,
)

logger = logging.getLogger(__name__)

review_router = APIRouter(prefix="/review", tags=["review"])


@review_router.get("/queue", response_model=ReviewQueueRead)
def queue(db: Session = Depends(get_db)) -> dict:
    return build_queue(db)


@review_router.post(
    "/conflicts/{conflict_id}/resolve", response_model=ConflictFlagRead
)
def resolve(
    conflict_id: int,
    req: ConflictResolveRequest,
    db: Session = Depends(get_db),
):
    try:
        flag = resolve_conflict(db, conflict_id, req.decision, req.resolved_by)
    except ReviewError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if flag is None:
        raise HTTPException(status_code=404, detail="conflict not found")
    db.commit()
    db.refresh(flag)
    logger.info(
        "api/review/conflicts/resolve: conflict %s -> %s (%s) by %s",
        flag.id,
        flag.status.value,
        flag.resolution,
        flag.resolved_by,
    )
    return flag


@review_router.post("/reports/{report_id}/decision", response_model=ReportRead)
def decide(
    report_id: int,
    req: ReportDecisionRequest,
    db: Session = Depends(get_db),
):
    try:
        report = decide_report(db, report_id, req.decision, req.comment)
    except ReviewError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    db.commit()
    db.refresh(report)
    logger.info(
        "api/review/reports/decision: report %s -> %s",
        report.id,
        report.status.value,
    )
    return report