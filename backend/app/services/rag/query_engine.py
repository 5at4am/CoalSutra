"""Answer a user question strictly from retrieved, cited chunks.

Pipeline: embed the question → hybrid-retrieve top-k chunks (see `retriever`) →
gate on evidence (if the best semantic similarity is below the threshold, say
so instead of answering from general knowledge) → ask the LLM to answer ONLY
from those chunks, citing `[document name, page N]` per claim → return the
answer plus the cited chunks (name + page + snippet).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.llm import LLMError, call_llm, embed_text
from app.services.rag import retriever

logger = logging.getLogger(__name__)

NO_EVIDENCE_MESSAGE = (
    "I could not find sufficient evidence in the ingested documents "
    "to answer this question."
)
SIMILARITY_THRESHOLD = 0.2


class QueryAnswer(BaseModel):
    """Strict schema the LLM must return — answer text only."""

    answer: str


def answer_question(
    session: Session,
    question: str,
    top_k: int = 5,
    embed: Callable[[str], list[float]] | None = None,
    llm: Callable[[str, type[BaseModel]], BaseModel] | None = None,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> dict:
    """Answer ``question`` grounded in retrieved chunks.

    ``embed``/``llm`` default to the real provider functions resolved at call
    time (so they can be monkeypatched end to end). Returns `{"answer": str,
    "citations": [{"document_name", "page_number", "snippet"}]}`. On LLM
    failure the retrieved citations are still returned, so the consumer can
    show sources even when answering breaks.
    """
    embed_fn = embed or embed_text
    llm_fn = llm or call_llm
    query_embedding = embed_fn(question)

    if (
        retriever.best_vector_similarity(session, query_embedding)
        < similarity_threshold
    ):
        logger.info(
            "query_engine: no evidence above %.2f for %r", similarity_threshold, question[:80]
        )
        return {"answer": NO_EVIDENCE_MESSAGE, "citations": []}

    chunks = retriever.retrieve(session, question, query_embedding, top_k=top_k)
    if not chunks:
        logger.info("query_engine: no chunks retrieved for %r", question[:80])
        return {"answer": NO_EVIDENCE_MESSAGE, "citations": []}

    citations = [
        {
            "document_name": chunk["document_name"],
            "page_number": chunk["page_number"],
            "snippet": chunk["text"],
        }
        for chunk in chunks
    ]

    prompt = _build_prompt(question, chunks)
    try:
        answer = llm_fn(prompt, QueryAnswer).answer
    except LLMError as exc:
        logger.warning("query_engine: LLM failed, returning citations only: %s", exc)
        answer = (
            "I retrieved the supporting evidence below but could not "
            "generate an answer (LLM provider unavailable)."
        )

    logger.info(
        "query_engine: answered %r from %d chunk(s)", question[:80], len(citations)
    )
    return {"answer": answer, "citations": citations}


def _build_prompt(question: str, chunks: list[dict]) -> str:
    parts = [
        "You are a strict extractive question-answering assistant. "
        "Answer the QUESTION using ONLY the SOURCE CHUNKS below.",
        (
            "Rules: "
            "1) Base every claim on the provided chunks; never use outside knowledge. "
            "2) Cite each claim as [document name, page N]. "
            "3) If the chunks do not contain the answer, say so explicitly. "
            "4) Be concise."
        ),
        "SOURCE CHUNKS:",
    ]
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[{index}] document={chunk['document_name']}, page={chunk['page_number']}\n"
            f"{chunk['text']}"
        )
    parts.append(f"QUESTION: {question}")
    parts.append('Respond ONLY with JSON in the form {"answer": "<your answer>"}.')
    return "\n\n".join(parts)