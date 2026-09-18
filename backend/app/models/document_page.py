"""One extracted page (or spreadsheet sheet) of a source document.

Sits between the **extract** and **store** stages in CLAUDE.md: the raw per-page
text and tables produced by the extractors, saved so every downstream consumer
(query/report/topics) reads the same intermediate representation and can cite
back to `document_id + page_number`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_page"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tables: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="pages")