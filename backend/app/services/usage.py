"""LLM usage telemetry: token counts, latency and errors, persisted per call.

Two entry points:

- ``llm_context(endpoint, label)`` — enter around a unit of work (a query, an
  evaluation run) so the next ``call_llm`` invocations inside it are attributed
  to that endpoint automatically. Labels are stored so the dashboard can show
  *what* the call was for.
- ``record_usage(...)`` — called by ``app.core.llm.call_llm`` for every provider
  round-trip (successful or not). Rows are written through their own short-lived
  session, so recording works from anywhere (routes, services, background
  threads) without coupling to a request's ``get_db`` session.

Best-effort by design: a telemetry failure must never take the answering path
down with it, so every persistence error is swallowed with a warning.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator

from app.core.database import SessionLocal
from app.models import LLMUsage

logger = logging.getLogger(__name__)

_endpoint: ContextVar[str] = ContextVar("llm_endpoint", default="generic")
_label: ContextVar[str | None] = ContextVar("llm_label", default=None)


@contextmanager
def llm_context(endpoint: str, label: str | None = None) -> Generator[None, None, None]:
    """Attribute everything under this block to ``endpoint`` (and optionally ``label``)."""
    token_e = _endpoint.set(endpoint)
    token_l = _label.set(label) if label is not None else None
    try:
        yield
    finally:
        _endpoint.reset(token_e)
        if token_l is not None:
            _label.reset(token_l)


def current_context() -> tuple[str, str | None]:
    """The active endpoint/label set by the caller (defaults if none)."""
    return _endpoint.get(), _label.get()


def record_usage(
    *,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: float = 0.0,
    success: bool = True,
    error: str | None = None,
    endpoint: str | None = None,
    prompt_label: str | None = None,
) -> None:
    """Persist one LLM call row. Never raises — telemetry is best-effort."""
    ep = endpoint or _endpoint.get()
    label = prompt_label if prompt_label is not None else _label.get()
    if label and len(label) > 240:
        label = label[:237] + "..."
    try:
        db = SessionLocal()
        try:
            db.add(
                LLMUsage(
                    endpoint=ep,
                    prompt_label=label,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    latency_ms=latency_ms,
                    success=success,
                    error=error,
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - telemetry must never break the caller
        logger.warning("usage: failed to persist LLM usage row", exc_info=True)