"""Topic modeling over the chunk corpus: numpy TF-IDF + KMeans, LLM-labeled.

Choice & why: BERTopic pulls scikit-learn + sentence-transformers + umap-learn +
hdbscan (hundreds of MB) and downloads a sentence-embedding model on first run —
too heavy and too network-dependent for the demo/CI environment. The spec's
fallback (TF-IDF + KMeans) is implemented here with **pure numpy** (already a
dependency through pandas), seeded and deterministic. Cluster labels come from
the LLM when configured, with a deterministic keyword fallback so the whole
path runs offline. Output per run is a list of
`{label, top_keywords, doc_count}` saved as a `TopicRun` row.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from collections.abc import Callable
from typing import Any

import numpy as np
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.llm import LLMError, call_llm
from app.models import DocumentChunk, TopicRun

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "or", "that", "the", "to",
    "was", "were", "will", "with",
}

_DEFAULT_N_TOPICS = 4
_MAX_FEATURES = 2000
_TOP_KEYWORDS = 5
_SEED = 42


class TopicLabels(BaseModel):
    labels: list[str]


def run_topic_model(
    session: Session,
    corpus_filter: dict[str, Any] | None = None,
    llm: Callable[[str, type[BaseModel]], BaseModel] | None = None,
) -> TopicRun:
    """Cluster corpus chunks into topics and persist a `TopicRun` row.

    ``corpus_filter`` supports: ``document_id``/``document_ids``, ``n_topics``,
    and optional ``labels`` (explicit label overrides, bypasses the LLM).
    """
    filters = corpus_filter or {}
    chunks = _pull_chunks(session, filters)
    topics = _cluster_chunks(chunks, filters, label_llm=llm)

    run = TopicRun(corpus_filter=filters, topics=topics)
    session.add(run)
    session.commit()
    session.refresh(run)
    logger.info(
        "topics: run %s produced %d topic(s) over %d chunk(s)",
        run.id,
        len(topics),
        len(chunks),
    )
    return run


def _pull_chunks(session: Session, filters: dict[str, Any]) -> list[dict]:
    query = session.query(DocumentChunk.id, DocumentChunk.document_id, DocumentChunk.text)
    document_ids = filters.get("document_ids") or (
        [filters["document_id"]] if filters.get("document_id") else None
    )
    if document_ids:
        query = query.filter(DocumentChunk.document_id.in_(document_ids))
    rows = query.order_by(DocumentChunk.id.asc()).limit(2000).all()
    return [
        {"chunk_id": chunk_id, "document_id": doc_id, "text": text}
        for chunk_id, doc_id, text in rows
    ]


def _cluster_chunks(
    chunks: list[dict],
    filters: dict[str, Any],
    label_llm: Callable[[str, type[BaseModel]], BaseModel] | None = None,
    max_features: int = _MAX_FEATURES,
    max_iter: int = 100,
) -> list[dict]:
    if not chunks:
        return []

    matrix, vocab, doc_tokens = _tfidf_matrix(chunks, max_features=max_features)
    n_clusters = min(
        max(int(filters.get("n_topics", _DEFAULT_N_TOPICS)), 1),
        len(chunks),
    )
    assignments = _kmeans(matrix, n_clusters=n_clusters, max_iter=max_iter)

    vocab_list = list(vocab)
    topics: list[dict] = []
    fallback_labels: list[str] = []
    for cluster in range(n_clusters):
        member_indices = np.where(assignments == cluster)[0]
        if len(member_indices) == 0:
            continue
        centroid = matrix[member_indices].mean(axis=0)
        order = np.argsort(centroid)[::-1][:_TOP_KEYWORDS]
        keywords = [vocab_list[i] for i in order if centroid[i] > 0]
        if not keywords:
            keywords = []
        doc_ids = {chunks[int(i)]["document_id"] for i in member_indices}
        top_term = keywords[0].title() if keywords else f"Topic {cluster + 1}"
        fallback_labels.append(f"Topic {cluster + 1}: {top_term}")
        topics.append(
            {
                "label": fallback_labels[-1],
                "top_keywords": keywords,
                "doc_count": len(doc_ids),
                "chunk_count": int(len(member_indices)),
            }
        )

    labeled = _assign_labels(topics, filters, label_llm)
    return [
        {**topic, "label": label}
        for topic, label in zip(topics, labeled)
    ]


def _assign_labels(
    topics: list[dict],
    filters: dict[str, Any],
    label_llm: Callable[[str, type[BaseModel]], BaseModel] | None,
) -> list[str]:
    fallback = [topic["label"] for topic in topics]
    if filters.get("labels"):
        explicit = list(filters["labels"])
        return [
            explicit[i] if i < len(explicit) else fallback[i]
            for i in range(len(topics))
        ]
    if not label_llm:
        return fallback

    prompt = _labels_prompt(topics, fallback)
    try:
        labels = label_llm(prompt, TopicLabels).labels
    except LLMError:
        logger.warning("topics: LLM labeling failed; using keyword fallback")
        return fallback
    return [
        labels[i] if i < len(labels) and labels[i].strip() else fallback[i]
        for i in range(len(topics))
    ]


def _labels_prompt(topics: list[dict], fallback: list[str]) -> str:
    lines = [
        "You name topic clusters for a mining-document knowledge base. "
        "Return a short (<=4 word) label per cluster.",
        "CLUSTERS:",
    ]
    for topic, fallback_label in zip(topics, fallback):
        lines.append(
            f"- keywords: {', '.join(topic['top_keywords']) or 'n/a'} "
            f"(suggested: {fallback_label!r})"
        )
    lines.append('Respond ONLY with JSON: {"labels": ["<label 1>", ...]}.')
    return "\n".join(lines)


# --- TF-IDF + KMeans (numpy) ----------------------------------------------


def _tokenize(text: str) -> list[str]:
    tokens = []
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if token not in _STOPWORDS and len(token) > 1:
            tokens.append(token)
    return tokens


def _tfidf_matrix(chunks: list[dict], max_features: int) -> tuple[np.ndarray, dict, list[list[str]]]:
    doc_tokens = [_tokenize(chunk["text"]) for chunk in chunks]
    doc_freq: Counter[str] = Counter()
    for tokens in doc_tokens:
        doc_freq.update(set(tokens))

    most_common = [term for term, _ in doc_freq.most_common(max_features)]
    vocab: dict[str, int] = {term: index for index, term in enumerate(most_common) if doc_freq[term] > 0}
    idf = {
        term: math.log(1.0 + len(chunks) / doc_freq[term])
        for term in vocab
    }

    matrix = np.zeros((len(chunks), len(vocab)), dtype=float)
    for row, tokens in enumerate(doc_tokens):
        counts = Counter(tokens)
        for term, count in counts.items():
            index = vocab.get(term)
            if index is not None:
                matrix[row, index] = count * idf[term]

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms
    return matrix, vocab, doc_tokens


def _kmeans(matrix: np.ndarray, n_clusters: int, max_iter: int = 100) -> np.ndarray:
    n_samples = matrix.shape[0]
    k = min(n_clusters, n_samples)
    rng = np.random.default_rng(_SEED)
    centers = matrix[rng.choice(n_samples, size=k, replace=False)].copy()

    assignments = np.zeros(n_samples, dtype=int)
    for _ in range(max_iter):
        distances = ((matrix[:, None, :] - centers[None, :, :]) ** 2).sum(axis=-1)
        new_assignments = distances.argmin(axis=1)
        next_centers = np.zeros_like(centers)
        for cluster in range(k):
            members = matrix[new_assignments == cluster]
            if len(members) > 0:
                next_centers[cluster] = members.mean(axis=0)
            else:
                next_centers[cluster] = centers[cluster]
        if np.array_equal(assignments, new_assignments):
            break
        assignments, centers = new_assignments, next_centers
    return assignments