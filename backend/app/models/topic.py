"""A single topic-modeling / word-cloud pass over a subset of the corpus.

Represents the **topics** consumer module in CLAUDE.md: given a corpus filter
(e.g. a date range or subsidiary), one run clusters documents and produces an
array of `{label, keywords, doc_count}` topics used by the dashboard.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TopicRun(Base):
    __tablename__ = "topic_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corpus_filter: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    topics: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)