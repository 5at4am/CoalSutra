"""A single, persisted model-evaluation run (golden-set accuracy over time).

`app.services.evaluation.run_evaluation` executes the golden cases from
`app.services.rag.eval` against the live retrieval pipeline (optionally adding
the LLM answer track) and stores the headline accuracy numbers plus the full
per-case scoring. The dashboard lists these runs to chart accuracy over time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # "retrieval" | "full" (retrieval + LLM answers)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="retrieval")
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    questions_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrieval_recall: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    answer_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    refusal_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    per_case: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )