"""Embed chunks and persist them as `DocumentChunk` rows.

The single swappable entry point is `embed_text` in `app/core/llm.py`; this
module only orchestrates chunk → embed → store and reports how many chunks were
written. Called from the ingestion orchestrator right after extraction so the
query layer never sees a document without retrieval coverage.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.llm import embed_text
from app.models import DocumentChunk
from app.services.rag.chunker import (
    DEFAULT_CHUNK_SIZE_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    chunk_pages,
)


def embed_and_store_chunks(
    session: Session,
    document_id: int,
    pages: list[dict],
    embed: Callable[[str], list[float]] = embed_text,
    chunk_size: int = DEFAULT_CHUNK_SIZE_TOKENS,
    overlap: int = DEFAULT_OVERLAP_TOKENS,
) -> int:
    """Chunk ``pages``, embed each chunk, persist as `DocumentChunk`, flush.

    Returns the number of chunks stored (0 when pages are empty). ``embed`` is
    injectable for tests; the default is the real provider-agnostic function.
    """
    chunks = chunk_pages(document_id, pages, chunk_size=chunk_size, overlap=overlap)
    for chunk in chunks:
        session.add(
            DocumentChunk(
                document_id=chunk["document_id"],
                page_number=chunk["page_number"],
                text=chunk["text"],
                embedding=embed(chunk["text"]),
            )
        )
    session.flush()
    return len(chunks)