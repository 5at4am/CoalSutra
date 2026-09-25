"""Hybrid retrieval over `document_chunks`: Postgres full-text + pgvector cosine.

On Postgres both signals run in SQL: `to_tsvector`/`ts_rank_cd` for the
BM25-ish text score and the pgvector `<=>` cosine operator for semantic
similarity. On other backends (SQLite in tests/CI) the same two signals are
computed in Python — BM25 for text, cosine for embeddings — so the module is
fully exercisable without a live Postgres.

The two ranked lists are merged by chunk id and re-ranked with a simple
weighted sum of normalized scores (`fts_weight` * norm(ts_rank) +
`vector_weight` * cosine_similarity).
"""

from __future__ import annotations

import logging
import math
from collections import Counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

_CANDIDATE_POOL = 15


def retrieve(
    session: Session,
    query_text: str,
    query_embedding: list[float],
    top_k: int = 5,
    fts_weight: float = 0.5,
    vector_weight: float = 0.5,
) -> list[dict]:
    """Return top-``top_k`` chunks ranked by a weighted FTS + vector merge.

    Each result dict has keys: `chunk_id, document_id, page_number, text,
    document_name, fts_score, vector_score, score`.
    """
    if session.bind.dialect.name == "postgresql":
        fts_candidates = _fts_candidates_pg(session, query_text, top_k)
        vec_candidates = _vector_candidates_pg(session, query_embedding, top_k)
    else:
        pool = _all_chunks(session)
        fts_candidates = _bm25_candidates(pool, query_text, top_k)
        vec_candidates = _cosine_candidates(pool, query_embedding, top_k)

    return _merge_rerank(fts_candidates, vec_candidates, top_k, fts_weight, vector_weight)


def best_vector_similarity(
    session: Session,
    query_embedding: list[float],
    pool_size: int = _CANDIDATE_POOL,
) -> float:
    """Highest cosine similarity of the query against any chunk (0.0 if none).

    Used by the query engine as the evidence gate: below the threshold it must
    answer "no evidence found" instead of answering from general knowledge.
    """
    if session.bind.dialect.name == "postgresql":
        candidates = _vector_candidates_pg(session, query_embedding, pool_size)
    else:
        candidates = _cosine_candidates(_all_chunks(session), query_embedding, pool_size)
    return max((candidate["score"] for candidate in candidates), default=0.0)


# --- Postgres (SQL) implementations -------------------------------------


def _fts_candidates_pg(session: Session, query_text: str, top_k: int) -> list[dict]:
    tsvector = func.to_tsvector(DocumentChunk.text)
    tsquery = func.plainto_tsquery(query_text)
    rank = func.ts_rank_cd(tsvector, tsquery)
    rows = (
        session.query(DocumentChunk, rank.label("score"))
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(tsvector.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(top_k)
        .all()
    )
    return [_candidate(chunk, float(score)) for chunk, score in rows]


def _vector_candidates_pg(
    session: Session, query_embedding: list[float], top_k: int
) -> list[dict]:
    literal = "[" + ",".join(str(x) for x in query_embedding) + "]"
    distance = DocumentChunk.embedding.cosine_distance(literal)
    rows = (
        session.query(DocumentChunk, distance.label("distance"))
        .join(Document, DocumentChunk.document_id == Document.id)
        .order_by(distance.asc())
        .limit(top_k)
        .all()
    )
    candidates = [
        _candidate(chunk, 1.0 - float(distance))
        for chunk, distance in rows
        if distance is not None
    ]
    return candidates


# --- Portable (Python) implementations ------------------------------------


def _all_chunks(session: Session) -> list[dict]:
    rows = (
        session.query(DocumentChunk, Document.filename)
        .join(Document, DocumentChunk.document_id == Document.id)
        .all()
    )
    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "page_number": chunk.page_number,
            "text": chunk.text,
            "document_name": filename,
            "embedding": chunk.embedding,
        }
        for chunk, filename in rows
    ]


def _bm25_candidates(
    chunks: list[dict], query_text: str, top_k: int, k1: float = 1.5, b: float = 0.75
) -> list[dict]:
    """Classic BM25 over the chunk corpus (portable stand-in for ts_rank)."""
    if not chunks:
        return []

    corpus_tokens = [_tokenize(c["text"]) for c in chunks]
    lengths = [len(tokens) for tokens in corpus_tokens]
    avg_len = sum(lengths) / len(lengths)
    doc_freq: Counter[str] = Counter()
    for tokens in corpus_tokens:
        doc_freq.update(set(tokens))

    query_terms = set(_tokenize(query_text))
    scored: list[dict] = []
    for chunk, tokens, length in zip(chunks, corpus_tokens, lengths):
        tf = Counter(tokens)
        score = 0.0
        for term in query_terms:
            freq = tf.get(term, 0)
            if freq == 0:
                continue
            idf = math.log(1.0 + (len(chunks) - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / avg_len))
        if score > 0:
            scored.append({**chunk, "score": score})
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]


def _cosine_candidates(
    chunks: list[dict], query_embedding: list[float], top_k: int
) -> list[dict]:
    if not query_embedding:
        return []
    q_norm = math.sqrt(sum(x * x for x in query_embedding)) or 1.0
    scored: list[dict] = []
    for chunk in chunks:
        vec = chunk.get("embedding")
        if vec is None or not len(vec):  # works for lists, Vector, and ndarrays
            continue
        norm = math.sqrt(sum(x * x for x in vec))
        if not norm:
            continue
        similarity = sum(a * b for a, b in zip(query_embedding, vec)) / (q_norm * norm)
        result = {k: v for k, v in chunk.items() if k != "embedding"}
        result["score"] = similarity
        scored.append(result)
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]


# --- Merge + re-rank ------------------------------------------------------


def _merge_rerank(
    fts_candidates: list[dict],
    vec_candidates: list[dict],
    top_k: int,
    fts_weight: float,
    vector_weight: float,
) -> list[dict]:
    by_id: dict[int, dict] = {}
    for candidate in [*fts_candidates, *vec_candidates]:
        by_id.setdefault(candidate["chunk_id"], candidate)

    best_fts = max((c["score"] for c in fts_candidates), default=0.0)
    merged: list[dict] = []
    for chunk_id, base in by_id.items():
        fts_score = next((c["score"] for c in fts_candidates if c["chunk_id"] == chunk_id), 0.0)
        vec_score = next((c["score"] for c in vec_candidates if c["chunk_id"] == chunk_id), 0.0)
        norm_fts = fts_score / best_fts if best_fts > 0 else 0.0
        merged.append(
            {
                **{k: v for k, v in base.items() if k != "embedding"},
                "fts_score": round(norm_fts, 6),
                "vector_score": round(vec_score, 6),
                "score": round(fts_weight * norm_fts + vector_weight * vec_score, 6),
            }
        )

    merged.sort(key=lambda c: c["score"], reverse=True)
    return merged[:top_k]


# --- helpers --------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _candidate(chunk: DocumentChunk, score: float) -> dict:
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "page_number": chunk.page_number,
        "text": chunk.text,
        "document_name": chunk.document.filename,
        "score": score,
    }