"""One embeddable chunk of a document page.

Sits behind the **query** pipeline stage in CLAUDE.md: page text is split into
~500-token overlapping chunks, each embedded into a pgvector ``vector`` column,
so the retriever can hybrid-match (full-text + cosine) and cite answers back to
`document_id + page_number`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        {"comment": "Embeddable chunks of page text for the query/retrieval stage"}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.EMBEDDING_DIM), nullable=True
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")