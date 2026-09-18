"""Grounded RAG question-answering endpoint.

Thin handler: delegates the whole pipeline to the query engine
(`app/services/rag/query_engine.py`). The answer is grounded in retrieved,
cited chunks — and explicitly refuses to answer from general knowledge when no
evidence is found above the similarity threshold.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import QueryRequest, QueryResponse
from app.services.query_metrics import record_query
from app.services.rag.query_engine import answer_question

query_router = APIRouter(prefix="/query", tags=["query"])


@query_router.post(
    "",
    response_model=QueryResponse,
    summary="Ask a question grounded in the ingested documents",
)
def ask(query: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    start = time.perf_counter()
    result = answer_question(db, query.question)
    record_query((time.perf_counter() - start) * 1000)
    return QueryResponse(**result)