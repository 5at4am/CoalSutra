"""Generic LLM call wrapper — the single place that talks to a model provider.

All modules (normalizer today, validator/query/report judges later) call
`call_llm(prompt, response_schema)` and never care which provider backs it.
Provider is isolated here, so swapping is one file + two Settings fields:

- current provider: OpenAI-compatible ``chat/completions`` (works against
  OpenAI directly, or any compatible gateway such as Ollama/vLLM/Azure via
  ``LLM_BASE_URL``).
- swap target: Anthropic (``messages`` API) or Vertex AI (``generateContent``)
  — same signature, same JSON + schema parsing.

Uses ``httpx`` (already a project dependency) so no new package is needed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the provider call or response parsing fails."""


class LLMDisabledError(LLMError):
    """Raised when no ``LLM_API_KEY`` is configured (caller may fall back)."""


def _parse_json_content(content: str, schema: type[BaseModel]) -> BaseModel:
    """Parse provider text into ``schema``, tolerating fenced code blocks."""
    candidates = [content]
    match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", content, re.DOTALL)
    if match:
        candidates.append(match.group(1))
    for candidate in candidates:
        try:
            return schema.model_validate_json(candidate)
        except ValidationError:
            continue
    raise LLMError(
        f"Provider returned unparseable JSON for {schema.__name__}: "
        f"{content[:300]!r}"
    )


def call_llm(prompt: str, response_schema: type[BaseModel]) -> BaseModel:
    """Send ``prompt`` to the configured model and validate against ``response_schema``."""
    if not settings.LLM_API_KEY:
        raise LLMDisabledError("LLM_API_KEY is not configured")

    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.LLM_MODEL,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        with httpx.Client(timeout=settings.LLM_TIMEOUT) as client:
            resp = client.post(
                url,
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LLMError(f"provider request failed: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"unexpected provider response shape: {data!r}") from exc

    logger.debug("call_llm: model=%s chars=%d", settings.LLM_MODEL, len(content))
    return _parse_json_content(content, response_schema)


def json_dumps(obj) -> str:
    """Compact JSON for prompt building."""
    return json.dumps(obj, ensure_ascii=False, default=str)


def embed_text(text: str) -> list[float]:
    """Embed a single ``text`` into ``EMBEDDING_DIM`` floats.

    Swappable single entry point for all embedding needs (mirrors
    ``call_llm``'s isolation). Supports two providers:

    - ``api`` (default): OpenAI-compatible ``/embeddings`` on ``LLM_BASE_URL``
      using ``EMBEDDING_MODEL``.
    - ``hash``: deterministic local hashing — used when the chat provider has
      no embedding endpoint (Groq, Ollama chat-only, offline demo).

    If an ``api`` call fails it degrades to the hash embedding with a warning
    instead of crashing the pipeline, so retrieval always keeps working.
    """
    if settings.EMBEDDING_PROVIDER == "hash" or not settings.LLM_API_KEY:
        return _hash_embedding(text, settings.EMBEDDING_DIM)

    url = f"{settings.LLM_BASE_URL.rstrip('/')}/embeddings"
    payload = {
        "model": settings.EMBEDDING_MODEL,
        "input": text,
    }
    try:
        with httpx.Client(timeout=settings.LLM_TIMEOUT) as client:
            resp = client.post(
                url,
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        vector: object = data["data"][0]["embedding"]
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning(
            "embed_text: %s; falling back to hash embeddings", exc
        )
        return _hash_embedding(text, settings.EMBEDDING_DIM)

    if (
        not isinstance(vector, list)
        or not vector
        or not all(isinstance(x, (int, float)) for x in vector)
    ):
        raise LLMError(f"unexpected embedding response shape: {str(data)[:300]!r}")

    logger.debug(
        "embed_text: model=%s dim=%d chars=%d",
        settings.EMBEDDING_MODEL,
        len(vector),
        len(text),
    )
    return [float(x) for x in vector]


def _hash_embedding(text: str, dim: int) -> list[float]:
    """Deterministic bag-of-char-bigrams hashed into a unit-L2 vector.

    Dimension-agnostic (works for any ``EMBEDDING_DIM``), stable across runs,
    and gives non-trivial cosine structure for docs sharing vocabulary — enough
    for offline demos and CI tests.
    """
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for token in tokens:
        grams = {token[i : i + 2] for i in range(len(token) - 1)} or {token}
        for gram in grams:
            digest = hashlib.md5(gram.encode("utf-8")).hexdigest()
            vec[int(digest[:8], 16) % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]