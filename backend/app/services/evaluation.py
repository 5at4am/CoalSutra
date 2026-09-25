"""Runnable golden-set evaluation that persists an ``EvalRun``.

Wraps the pure scoring helpers in ``app.services.rag.eval`` with the live
retrieval pipeline — embed the question, gate on the evidence threshold,
retrieve chunks, then score. Optionally adds the LLM answer track
(``with_answers=True``) which also flows through ``llm_context("eval_answer")`
so the token telemetry attributes those calls to the evaluation.

Each run is saved, letting the Evaluate dashboard chart model accuracy over
time instead of showing a single snapshot.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm import embed_text
from app.models import Document, EvalRun
from app.services.rag import retriever
from app.services.rag.eval import GOLDEN_CASES, aggregate, score_answer, score_retrieval
from app.services.rag.query_engine import answer_question
from app.services.usage import llm_context

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.2


def run_evaluation(
    session: Session,
    *,
    with_answers: bool = False,
    top_k: int = 5,
    embed: Callable[[str], list[float]] | None = None,
    llm: Callable[[str, type[Any]], Any] | None = None,
) -> EvalRun:
    """Evaluate every golden case against the store and persist an ``EvalRun``.

    ``embed``/``llm`` default to the real provider functions (monkeypatchable for
    hermetic tests). One case failing to answer never aborts the whole run —
    the failure is captured on that case's row.
    """
    embed_fn = embed or embed_text
    known_docs = {filename for (filename,) in session.query(Document.filename).all()}
    rows: list[dict[str, Any]] = []
    start = time.perf_counter()

    for case in GOLDEN_CASES:
        query_embedding = embed_fn(case["question"])
        if (
            retriever.best_vector_similarity(session, query_embedding)
            < SIMILARITY_THRESHOLD
        ):
            chunks: list[dict[str, Any]] = []
        else:
            chunks = retriever.retrieve(
                session, case["question"], query_embedding, top_k=top_k
            )

        row: dict[str, Any] = {"id": case["id"], "question": case["question"]}
        row.update(score_retrieval(case, chunks))

        if with_answers:
            try:
                with llm_context("eval_answer", case["id"]):
                    result = answer_question(
                        session,
                        case["question"],
                        top_k=top_k,
                        embed=embed_fn,
                        llm=llm,
                    )
            except Exception as exc:  # noqa: BLE001 - one case must not sink a run
                row["answer_error"] = str(exc)
                row["answer_ok"] = False
                row["answer"] = ""
            else:
                scored = score_answer(
                    case,
                    result["answer"],
                    result.get("citations", []),
                    known_docs=known_docs,
                )
                row["answer_ok"] = scored["ok"]
                row["answer"] = result["answer"][:400]
                if case.get("expect_refusal"):
                    row["refused"] = scored.get("refused", False)

        rows.append(row)

    summary, answer_accuracy, refusal_passed = _headline_stats(
        rows, full_mode=with_answers
    )
    run = EvalRun(
        mode="full" if with_answers else "retrieval",
        model=settings.LLM_MODEL if with_answers else None,
        questions_evaluated=len(rows),
        passed=summary["passed"],
        retrieval_recall=summary.get("retrieval_recall", 0.0),
        answer_accuracy=answer_accuracy,
        refusal_passed=refusal_passed,
        per_case=rows,
        summary=summary,
        duration_ms=round((time.perf_counter() - start) * 1000, 1),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _headline_stats(
    rows: list[dict[str, Any]], *, full_mode: bool
) -> tuple[dict[str, Any], float | None, bool | None]:
    """Aggregate per-case rows into headline accuracy numbers.

    ``retrieval_recall`` averages over the value-seeking retrieval cases only
    (refusal control contributes to ``passed`` but not the denominator), then
    the answer track adds ``answer_accuracy`` over its value cases and reports
    the refusal control separately.
    """
    summary = aggregate(rows)

    answer_accuracy: float | None = None
    refusal_passed: bool | None = None
    if full_mode:
        answer_rows = [row for row in rows if "answer_ok" in row]
        value_answers = [
            row for row in answer_rows if not row.get("expect_refusal_is_control")
        ]
        if value_answers:
            answer_accuracy = round(
                sum(1 for row in value_answers if row["answer_ok"])
                / len(value_answers),
                3,
            )
        refusal = next(
            (r for r in answer_rows if r.get("expect_refusal_is_control")), None
        )
        if refusal is not None:
            refusal_passed = bool(refusal.get("answer_ok"))

    return summary, answer_accuracy, refusal_passed