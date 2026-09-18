"""Schemas for the human-in-the-loop review queue."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConflictResolveRequest(BaseModel):
    decision: Literal["fact_a", "fact_b", "both", "neither"]
    resolved_by: str = Field(min_length=1)


class ReportDecisionRequest(BaseModel):
    decision: Literal["approve", "send_back"]
    comment: str = ""


class FactQueueItem(BaseModel):
    fact_id: int
    entity: str
    value: str
    unit: str | None = None
    date_reference: str | None = None
    page_number: int | None = None
    document_name: str
    snippet: str
    confidence: float


class ConflictQueueItem(BaseModel):
    id: int
    status: str
    reason: str
    resolution: str | None = None
    resolved_by: str | None = None
    fact_a: FactQueueItem
    fact_b: FactQueueItem


class DraftReportItem(BaseModel):
    id: int
    title: str
    template_type: str
    generated_at: datetime
    status: str
    summary: str


class ReviewQueueRead(BaseModel):
    conflicts: list[ConflictQueueItem]
    draft_reports: list[DraftReportItem]