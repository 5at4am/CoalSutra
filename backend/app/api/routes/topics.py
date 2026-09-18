"""Topic-run endpoints: run, get by id, get latest.

Thin handlers over `app/services/topics/`. `POST /run` triggers a clustering
pass on the requested corpus filter and persists it as a `TopicRun`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import TopicRun
from app.schemas import TopicRead
from app.services.topics.topic_model import run_topic_model

topics_router = APIRouter(prefix="/topics", tags=["topics"])


class TopicRunRequest(BaseModel):
    corpus_filter: dict[str, Any] = Field(default_factory=dict)
    n_clusters: int = Field(default=4, ge=1, le=20)


@topics_router.post("/run", response_model=TopicRead, status_code=201)
def run(req: TopicRunRequest, db: Session = Depends(get_db)) -> TopicRun:
    filters = dict(req.corpus_filter)
    filters.setdefault("n_topics", req.n_clusters)
    return run_topic_model(db, filters)


@topics_router.get("/latest", response_model=TopicRead)
def latest_run(db: Session = Depends(get_db)) -> TopicRun:
    run = db.query(TopicRun).order_by(TopicRun.id.desc()).first()
    if run is None:
        raise HTTPException(status_code=404, detail="no topic runs yet")
    return run


@topics_router.get("/{run_id}", response_model=TopicRead)
def get_run(run_id: int, db: Session = Depends(get_db)) -> TopicRun:
    run = db.get(TopicRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="topic run not found")
    return run