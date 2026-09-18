"""Read endpoints over the validated store: extracted facts and conflict flags.

Thin handlers (no business logic) — query the store and return schemas. The
conflict queue powers the human-in-the-loop review gate: anything flagged as
`open` must be resolved before its facts feed report generation.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ConflictFlag, ExtractedFact
from app.models.enums import ConflictStatus
from app.schemas import ConflictFlagRead, ExtractedFactRead

facts_router = APIRouter(prefix="/facts", tags=["facts"])
conflicts_router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@facts_router.get("", response_model=list[ExtractedFactRead], summary="List extracted facts")
def list_facts(
    entity: Optional[str] = None,
    document_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> list[ExtractedFact]:
    query = db.query(ExtractedFact).order_by(ExtractedFact.id.desc())
    if entity:
        query = query.filter(ExtractedFact.entity == entity)
    if document_id is not None:
        query = query.filter(ExtractedFact.document_id == document_id)
    return query.all()


@conflicts_router.get(
    "", response_model=list[ConflictFlagRead], summary="List conflict flags"
)
def list_conflicts(
    status: Optional[ConflictStatus] = None,
    db: Session = Depends(get_db),
) -> list[ConflictFlag]:
    query = db.query(ConflictFlag).order_by(ConflictFlag.id.desc())
    if status is not None:
        query = query.filter(ConflictFlag.status == status)
    return query.all()