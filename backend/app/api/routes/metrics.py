"""Dashboard metrics: a single summary payload for the metrics row.

Aggregates are computed directly from the existing store — document counts,
open conflicts, documents implicated in any cross-source conflict, and the
in-process average query latency. No new tables.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ConflictFlag, Document, ExtractedFact
from app.models.enums import ConflictStatus, DocumentStatus
from app.schemas import MetricsSummaryRead
from app.services.query_metrics import average_query_ms, queries_served

metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])


@metrics_router.get("/summary", response_model=MetricsSummaryRead)
def summary(db: Session = Depends(get_db)) -> MetricsSummaryRead:
    documents_total = db.query(func.count(Document.id)).scalar() or 0
    documents_processed = (
        db.query(func.count(Document.id))
        .filter(Document.status == DocumentStatus.processed)
        .scalar()
        or 0
    )
    open_conflicts = (
        db.query(func.count(ConflictFlag.id))
        .filter(ConflictFlag.status == ConflictStatus.open)
        .scalar()
        or 0
    )

    flagged_rows = (
        db.query(ExtractedFact.document_id)
        .join(
            ConflictFlag,
            or_(
                ConflictFlag.fact_a_id == ExtractedFact.id,
                ConflictFlag.fact_b_id == ExtractedFact.id,
            ),
        )
        .filter(ExtractedFact.document_id.isnot(None))
        .all()
    )
    flagged_documents = len({row[0] for row in flagged_rows})
    flagged_pct = (
        round(100.0 * flagged_documents / documents_processed, 1)
        if documents_processed
        else 0.0
    )

    return MetricsSummaryRead(
        documents_total=documents_total,
        documents_processed=documents_processed,
        open_conflicts=open_conflicts,
        flagged_documents_pct=flagged_pct,
        avg_query_ms=average_query_ms(),
        queries_served=queries_served(),
    )