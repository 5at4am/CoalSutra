"""LLM telemetry + evaluation endpoints for the Evaluate dashboard.

Two persistence-backed surfaces:

- ``/usage/*`` — token counts, latency, success rate and a cost estimate from
  the ``llm_usage`` log that every ``call_llm`` write to.
- ``/eval/*`` — run and list golden-set evaluation runs (``eval_runs``).

Both are read-only over the store; evaluations are the only write surface in
this router and they persist a fresh run each time.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import EvalRun, LLMUsage
from app.schemas import (
    EndpointUsageRead,
    EvalRunRead,
    EvalRunStartRequest,
    LlmUsageCallRead,
    LlmUsageSummaryRead,
)
from app.services.evaluation import run_evaluation

llm_router = APIRouter(prefix="/llm", tags=["llm"])


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        1e-6
        * (
            prompt_tokens * settings.LLM_PRICE_PER_1M_INPUT_USD
            + completion_tokens * settings.LLM_PRICE_PER_1M_OUTPUT_USD
        ),
        6,
    )


@llm_router.get("/usage/summary", response_model=LlmUsageSummaryRead)
def usage_summary(db: Session = Depends(get_db)) -> LlmUsageSummaryRead:
    """Aggregate all recorded usage into headline totals + a per-endpoint split."""
    rows = db.query(LLMUsage).all()

    per_endpoint: dict[str, dict] = {}
    for row in rows:
        ep = per_endpoint.setdefault(
            row.endpoint,
            {
                "endpoint": row.endpoint,
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "latency_total_ms": 0.0,
                "success_calls": 0,
                "latency_samples": 0,
            },
        )
        ep["calls"] += 1
        ep["prompt_tokens"] += row.prompt_tokens
        ep["completion_tokens"] += row.completion_tokens
        ep["total_tokens"] += row.total_tokens
        if row.latency_ms:
            ep["latency_total_ms"] += row.latency_ms
            ep["latency_samples"] += 1
        if row.success:
            ep["success_calls"] += 1

    by_endpoint: list[EndpointUsageRead] = []
    for ep in per_endpoint.values():
        by_endpoint.append(
            EndpointUsageRead(
                endpoint=ep["endpoint"],
                calls=ep["calls"],
                total_tokens=ep["total_tokens"],
                prompt_tokens=ep["prompt_tokens"],
                completion_tokens=ep["completion_tokens"],
                estimated_cost_usd=_estimate_cost(
                    ep["prompt_tokens"], ep["completion_tokens"]
                ),
                avg_latency_ms=round(ep["latency_total_ms"] / ep["latency_samples"], 1)
                if ep["latency_samples"]
                else None,
                success_rate=round(100.0 * ep["success_calls"] / ep["calls"], 1)
                if ep["calls"]
                else 0.0,
            )
        )

    total_prompt = sum(ep["prompt_tokens"] for ep in per_endpoint.values())
    total_completion = sum(ep["completion_tokens"] for ep in per_endpoint.values())
    total_calls = sum(ep["calls"] for ep in per_endpoint.values())
    total_latency = sum(ep["latency_total_ms"] for ep in per_endpoint.values())
    total_latency_samples = sum(ep["latency_samples"] for ep in per_endpoint.values())
    success_calls = sum(ep["success_calls"] for ep in per_endpoint.values())

    return LlmUsageSummaryRead(
        total_calls=total_calls,
        total_tokens=total_prompt + total_completion,
        prompt_tokens=total_prompt,
        completion_tokens=total_completion,
        avg_latency_ms=round(total_latency / total_latency_samples, 1)
        if total_latency_samples
        else None,
        success_rate=round(100.0 * success_calls / total_calls, 1)
        if total_calls
        else 0.0,
        failed_calls=total_calls - success_calls,
        estimated_cost_usd=_estimate_cost(total_prompt, total_completion),
        by_endpoint=by_endpoint,
    )


@llm_router.get("/usage/calls", response_model=list[LlmUsageCallRead])
def usage_calls(
    limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)
) -> list[LlmUsageCallRead]:
    """Most recent LLM calls, newest first."""
    rows = (
        db.query(LLMUsage).order_by(LLMUsage.id.desc()).limit(limit).all()
    )
    return [LlmUsageCallRead.model_validate(row) for row in rows]


@llm_router.post("/eval/run", response_model=EvalRunRead)
def eval_run(
    req: EvalRunStartRequest, db: Session = Depends(get_db)
) -> EvalRunRead:
    """Run the golden-set evaluation against the current store and persist it."""
    run = run_evaluation(db, with_answers=req.with_answers)
    return EvalRunRead.model_validate(run)


@llm_router.get("/eval/runs", response_model=list[EvalRunRead])
def eval_runs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)) -> list[EvalRunRead]:
    rows = db.query(EvalRun).order_by(EvalRun.id.desc()).limit(limit).all()
    return [EvalRunRead.model_validate(row) for row in rows]


@llm_router.get("/eval/runs/{run_id}", response_model=EvalRunRead)
def eval_run_detail(run_id: int, db: Session = Depends(get_db)) -> EvalRunRead:
    run = db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return EvalRunRead.model_validate(run)