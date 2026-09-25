"""Seed the shipped demo.db with evaluation + usage telemetry.

Run against the checked-in demo store from `backend/`:

    $env:DATABASE_URL='sqlite:///data/seed_demo/demo.db'
    python -m scripts.seed_llm_demo

The stored corpus is hash-embedded (matches the demo's EMBEDDING_PROVIDER), so
the retrieval-only evaluation scores real, reproducible accuracy numbers.
Usage rows are synthetic but transparently labelled "[demo seed]". Both seeds
are idempotent — re-running adds nothing.
"""

from __future__ import annotations

import os
from pathlib import Path

DEMO_DB = Path(__file__).resolve().parent.parent / "data" / "seed_demo" / "demo.db"


def main() -> None:
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{DEMO_DB}")
    os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
    os.environ.setdefault("LLM_API_KEY", "")

    from app.core.database import Base, SessionLocal, engine
    from app.models import EvalRun, LLMUsage
    from app.services.evaluation import run_evaluation

    Base.metadata.create_all(engine)
    db = SessionLocal()

    # 1) one real evaluation run (only if the store is not seeded already)
    if db.query(EvalRun.id).first() is None:
        run = run_evaluation(db, with_answers=False)
        print(
            f"eval: run #{run.id} retrieval_recall={run.retrieval_recall:.2f} "
            f"passed={run.passed}/{run.questions_evaluated}"
        )
    else:
        print("eval: already seeded, skipping")

    # 2) labelled usage rows (idempotent)
    if db.query(LLMUsage.id).first() is None:
        rows = [
            LLMUsage(
                endpoint="query",
                prompt_label="[demo seed] What was the total geological reserve of the Barkhola coal block as of 31 March 2026?",
                model="gpt-4o-mini",
                prompt_tokens=640,
                completion_tokens=96,
                total_tokens=736,
                latency_ms=812.0,
                success=True,
            ),
            LLMUsage(
                endpoint="query",
                prompt_label="[demo seed] What is the thickness of the coal seam?",
                model="gpt-4o-mini",
                prompt_tokens=312,
                completion_tokens=54,
                total_tokens=366,
                latency_ms=641.0,
                success=True,
            ),
            LLMUsage(
                endpoint="query",
                prompt_label="[demo seed] What was the average core recovery percentage in the boreholes?",
                model="gpt-4o-mini",
                prompt_tokens=405,
                completion_tokens=112,
                total_tokens=517,
                latency_ms=938.0,
                success=True,
            ),
            LLMUsage(
                endpoint="report",
                prompt_label="[demo seed] Generate reserve estimate report",
                model="gpt-4o-mini",
                prompt_tokens=2380,
                completion_tokens=1102,
                total_tokens=3482,
                latency_ms=4240.0,
                success=False,
                error="provider request failed: HTTP 429 rate limited",
            ),
        ]
        db.add_all(rows)
        db.commit()
        print("usage: seeded 4 labelled rows")
    else:
        print("usage: already seeded, skipping")

    db.close()


if __name__ == "__main__":
    main()