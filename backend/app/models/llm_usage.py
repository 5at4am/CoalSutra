"""One persisted LLM round-trip — the atomic unit of the accuracy/token dashboard.

Every `call_llm` records a row here (via `app.services.usage`), whether the
call succeeded or failed: token counts, latency, the endpoint that triggered
it (query / evaluation / report…) and a short label. This is the data store the
"Evaluate" dashboard reads to report model accuracy, efficiency and spend.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(
        String(32), nullable=False, default="generic", index=True
    )
    prompt_label: Mapped[str | None] = mapped_column(String(240), nullable=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )