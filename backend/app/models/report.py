"""One auto-generated, template-filled report.

Represents the **report** consumer module in CLAUDE.md: structured content
(JSON sections, each holding citations back to source documents) generated
from approved, validated facts. `export_path` holds the rendered PDF/Word
file once the report is finalized.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ReportStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, native_enum=False),
        nullable=False,
        default=ReportStatus.draft,
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    export_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    review_note: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Reviewer comment when a draft is sent back",
    )