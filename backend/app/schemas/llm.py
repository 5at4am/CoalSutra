from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class EndpointUsageRead(BaseModel):
    endpoint: str
    calls: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    avg_latency_ms: Optional[float] = None
    success_rate: float


class LlmUsageSummaryRead(BaseModel):
    total_calls: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    avg_latency_ms: Optional[float] = None
    success_rate: float
    failed_calls: int
    estimated_cost_usd: float
    by_endpoint: list[EndpointUsageRead]


class LlmUsageCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    endpoint: str
    prompt_label: Optional[str] = None
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    success: bool
    error: Optional[str] = None
    created_at: datetime


class EvalRunStartRequest(BaseModel):
    with_answers: bool = False


class EvalCaseRead(BaseModel):
    id: str
    question: str
    ok: bool
    retrieval_recall: float
    values_in_retrieved: list[float]
    docs_in_retrieved: list[str]
    expect_refusal_is_control: bool = False
    answer_ok: Optional[bool] = None
    answer: Optional[str] = None
    expected_values: Optional[list[float]] = None


class EvalRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: str
    model: Optional[str] = None
    questions_evaluated: int
    passed: int
    retrieval_recall: float
    answer_accuracy: Optional[float] = None
    refusal_passed: Optional[bool] = None
    summary: dict[str, Any]
    duration_ms: float
    created_at: datetime
    per_case: list[dict[str, Any]]