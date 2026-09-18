"""A detected contradiction between two extracted facts.

Represents the **validate** pipeline stage in CLAUDE.md: rules + LLM
cross-checks new extractions against what is already stored, and anything
conflicting is flagged for the human-in-the-loop review queue instead of
silently overwriting one number with another.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ConflictStatus

if TYPE_CHECKING:
    from app.models.fact import ExtractedFact


class ConflictFlag(Base):
    __tablename__ = "conflict_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_a_id: Mapped[int] = mapped_column(
        ForeignKey("extracted_facts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fact_b_id: Mapped[int] = mapped_column(
        ForeignKey("extracted_facts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ConflictStatus] = mapped_column(
        Enum(ConflictStatus, native_enum=False),
        nullable=False,
        default=ConflictStatus.open,
    )
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="Reviewer verdict: fact_a | fact_b | both | neither",
    )

    fact_a: Mapped["ExtractedFact"] = relationship(
        back_populates="flags_a", foreign_keys=[fact_a_id]
    )
    fact_b: Mapped["ExtractedFact"] = relationship(
        back_populates="flags_b", foreign_keys=[fact_b_id]
    )