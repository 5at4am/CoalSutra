"""Chunk page text into ~500-token windows with a small overlap.

Token count is approximated by whitespace-separated words — good enough for
embedding-size budgeting on English technical text. Each chunk keeps its
`(document_id, page_number)` so retrieval can cite back to the source page.
"""

from __future__ import annotations

DEFAULT_CHUNK_SIZE_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 50


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_TOKENS,
    overlap: int = DEFAULT_OVERLAP_TOKENS,
) -> list[str]:
    """Split ``text`` into overlapping token windows.

    Windows advance by ``chunk_size - overlap`` tokens so consecutive chunks
    share the overlap region (avoids cutting mid-thought at boundaries, which
    is what the embedding needs from a retrieval standpoint).
    """
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be smaller than chunk_size ({chunk_size})")

    tokens = text.split()
    if not tokens:
        return []

    step = max(chunk_size - overlap, 1)
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(" ".join(tokens[start:end]))
        if end == len(tokens):
            break
        start += step
    return chunks


def chunk_pages(
    document_id: int,
    pages: list[dict],
    chunk_size: int = DEFAULT_CHUNK_SIZE_TOKENS,
    overlap: int = DEFAULT_OVERLAP_TOKENS,
) -> list[dict]:
    """Chunk every page of ``pages`` into `{document_id, page_number, text}` dicts.

    Empty pages produce no chunks. `pages` is the extractor output shape:
    a list of dicts with ``page_number`` and ``text`` keys.
    """
    chunks: list[dict] = []
    for page in pages:
        for piece in chunk_text(page.get("text", ""), chunk_size, overlap):
            chunks.append(
                {
                    "document_id": document_id,
                    "page_number": page["page_number"],
                    "text": piece,
                }
            )
    return chunks