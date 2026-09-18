"""One normalized extraction from a source document.

This is the heart of the **normalize** pipeline stage in CLAUDE.md — every
figure from any source format is flattened into the same shape:
`entity, value, unit, date, source document + page`. `raw_snippet` preserves
the exact source text, and `confidence` feeds the validate stage and the
accuracy metrics the SIH rubric measures.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.conflict import ConflictFlag
    from app.models.document import Document


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    date_reference: Mapped[date | None] = mapped_column(Date, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="facts")

    flags_a: Mapped[list["ConflictFlag"]] = relationship(
        back_populates="fact_a",
        foreign_keys="ConflictFlag.fact_a_id",
        cascade="all, delete-orphan",
    )
    flags_b: Mapped[list["ConflictFlag"]] = relationship(
        back_populates="fact_b",
        foreign_keys="ConflictFlag.fact_b_id",
        cascade="all, delete-orphan",
    )