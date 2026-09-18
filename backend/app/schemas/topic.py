from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TopicRunRequest(BaseModel):
    corpus_filter: dict[str, Any]


class TopicRunCreate(BaseModel):
    corpus_filter: dict[str, Any]
    topics: list[dict[str, Any]]


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    corpus_filter: dict[str, Any]
    generated_at: datetime
    topics: list[dict[str, Any]]