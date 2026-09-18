"""LLM-based normalizer: page text -> ExtractedFact-shaped dicts.

Primary extraction path is a strict, zero-temperature LLM call (see
`SYSTEM_PROMPT`) that returns JSON matching the ExtractedFact schema and copies
the `raw_snippet` verbatim from the source text for traceability. When no LLM
is configured (`LLM_API_KEY` empty) or the provider call fails, we fall back to
the deterministic rule-based extractor so the pipeline never hard-fails on
offline/dev machines.

Every returned dict is sanitized (document_id attached, page_number pinned,
value coerced to str, date parsed, confidence clamped) so the orchestrator can
pass it straight to `ExtractedFact(**fact)`.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.core.llm import LLMError, LLMDisabledError, call_llm, json_dumps

logger = logging.getLogger(__name__)

# Soft catalog of domain labels. The extractor prefers these to keep entity
# naming consistent across documents and runs (zero-shot labels drift otherwise);
# it may still add a new label when none of these truly fit.
PREFERRED_ENTITIES = (
    "reserves: coal_reserve, total_geological_reserve, proved_reserve, "
    "indicated_reserve, inferred_reserve, seam_ii/iii/iv_reserve "
    "production: production, tonnes_extracted, ore_raised, despatch "
    "quality: ash_content, moisture, mn_grade, fe_percent, si02_percent, "
    "volatile_matter, gross_calorific_value, sulphur, specific_gravity, "
    "seam_thickness, core_recovery "
    "mining: overburden_ratio, stripping_ratio, shift_days, "
    "avg_tonnes_per_day, borehole_count, pits_count, capacity"
)

SYSTEM_PROMPT = """\
You are a strict fact-extraction engine for coal-mining and geological survey
documents (CMPDI/CIL style reports). You receive raw page text and return ONLY
structured facts that are EXPLICITLY stated in that text.

HARD RULES
1. Extract only facts stated verbatim. NEVER infer, calculate, average, or use
   outside knowledge. If a number could be something else, skip it.
2. Every fact MUST carry a `raw_snippet` copied character-for-character from the
   provided text — this is the traceability contract back to the source page.
3. `entity`: short snake_case label for the figure, e.g. proved_reserve,
   geological_reserve, overburden_ratio, ash_content, moisture, production,
   capacity. Reuse the same label for the same kind of figure.
4. `value`: the exact numeric figure as a string, WITHOUT the unit. Keep
   decimals. A comma is ALWAYS a thousands separator in these documents
   ("1,240" -> "1240") and NEVER a decimal point — so "2,960" is 2960, never 2.960.
5. `unit`: one of MT, MTPA, Mt, %, m, mm, ha, m³, t, INR crore, INR lakh.
   Use null when the figure genuinely has no unit (e.g. a ratio).
6. `date_reference`: the reporting/as-of date IF the text states one — ISO
   YYYY-MM-DD for a full date, bare YYYY for a year. Also emit a date for table
   rows that carry a month+year (e.g. "March 1988" -> "1988-03-01", "Jan 2024"
   -> "2024-01-01"); the month+year printed in the row IS the fact's date even
   when the value sits in a neighbouring cell/column of the same row.
7. `page_number`: use exactly the page number given to you.
8. `confidence`: 0.0-1.0 encoding how explicit the extraction is. When unsure,
   lower it AND still prefer to skip.
9. SKIP: numbers without an identifiable entity, derived/averaged totals not
   clearly stated, table cells that are identifiers or years, and anything you
   are not confident about. Fewer accurate facts beat many guesses.

Return ONLY JSON in this shape:
{"facts": [{"entity": "...", "value": "1234", "unit": "MT",
            "date_reference": "2023-01-01" | null, "page_number": 1,
            "raw_snippet": "exact copied text", "confidence": 0.95}]}
"""


class _LlmFact(BaseModel):
    entity: str = Field(min_length=1)
    value: str | int | float
    unit: str | None = None
    date_reference: str | None = None
    page_number: int | None = None
    raw_snippet: str = Field(min_length=1)
    confidence: float = Field(default=0.5)


class _LlmFactBatch(BaseModel):
    facts: list[_LlmFact] = Field(default_factory=list)


def _parse_date_reference(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    if raw.isdigit() and len(raw) == 4:
        return date(int(raw), 1, 1)
    try:
        return date.fromisoformat(raw)
    except ValueError:
        logger.warning("normalizer: unparseable date_reference %r ignored", raw)
        return None


def _repair_thousands_decimal(value: str, snippet: str) -> str:
    """Safety net for a known OCR+LLM slip: "2,960" (thousands) read as "2.960".

    When the verbatim snippet carries a thousands-separated form whose digits
    exactly match a three-decimal LLM value, the snippet is the source of truth.
    """
    if re.fullmatch(r"[0-9]{1,3}\.[0-9]{3}", value) and snippet:
        digits = value.replace(".", "")
        for m in re.finditer(r"([0-9]{1,3}),([0-9]{3})\b", snippet):
            if m.group(1) + m.group(2) == digits:
                return digits
    return value


def _coerce_facts(batch: _LlmFactBatch, document_id: int, page_number: int) -> list[dict]:
    """Flatten an LLM batch into ExtractedFact-compatible dicts."""
    facts = []
    for item in batch.facts:
        if not item.entity.strip() or not item.raw_snippet.strip():
            continue
        value = _repair_thousands_decimal(
            str(item.value).replace(",", "").strip(), item.raw_snippet
        )
        facts.append(
            {
                "document_id": document_id,
                "entity": item.entity.strip().lower().replace(" ", "_"),
                "value": value,
                "unit": item.unit.strip() if item.unit else None,
                "date_reference": _parse_date_reference(item.date_reference),
                "page_number": page_number,
                "raw_snippet": item.raw_snippet.strip(),
                "confidence": max(0.0, min(1.0, item.confidence)),
            }
        )
    return facts


def _llm_user_prompt(page_number: int, text: str) -> str:
    return (
        f"Extract facts from page {page_number}.\n\n"
        f"PAGE NUMBER: {page_number}\n"
        f"PAGE TEXT:\n{text}\n\n"
        "Respond with JSON only, matching this schema:\n"
        + json_dumps(
            {
                "facts": [
                    {
                        "entity": "snake_case_label",
                        "value": "string_number_without_unit",
                        "unit": "MT | MTPA | % | m | mm | ha | m³ | t | INR crore | INR lakh | null",
                        "date_reference": "YYYY-MM-DD | YYYY | null",
                        "page_number": page_number,
                        "raw_snippet": "verbatim text from the page",
                        "confidence": 0.95,
                    }
                ]
            }
        )
    )


def _extract_page_with_llm(
    document_id: int,
    page_number: int,
    text: str,
    llm: Callable[[str, type[BaseModel]], BaseModel],
) -> list[dict]:
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"\nPREFERRED ENTITY LABELS — use these when one of them fits "
        f"(keeps the fact store consistent across documents): "
        f"{PREFERRED_ENTITIES}\n"
        f"\n--- USER MESSAGE ---\n{_llm_user_prompt(page_number, text)}"
    )
    try:
        batch = llm(prompt, _LlmFactBatch)
    except (LLMDisabledError, LLMError):
        raise
    if not isinstance(batch, _LlmFactBatch):
        raise LLMError("llm returned wrong schema instance")
    return _coerce_facts(batch, document_id, page_number)


def facts_from_pages(
    document_id: int,
    pages: list[dict],
    llm: Callable[[str, type[BaseModel]], BaseModel] = call_llm,
) -> list[dict]:
    """Extract facts for a document. LLM-first, rule-based fallback.

    ``pages`` is the extractor output (`{page_number, text, tables}` records).
    Returns a flat list of sanitized dicts ready for `ExtractedFact(**fact)`.
    """
    facts: list[dict] = []

    for page in pages:
        page_number = page.get("page_number", 1)
        text = (page.get("text") or "").strip()
        if not text:
            continue
        try:
            facts.extend(
                _extract_page_with_llm(document_id, page_number, text, llm)
            )
        except LLMDisabledError:
            logger.info(
                "normalizer: LLM not configured — using rule-based fallback "
                "for document %s", document_id
            )
            return _rule_fallback(document_id, pages)
        except LLMError as exc:
            logger.warning(
                "normalizer: LLM extraction failed (%s) — rule fallback for "
                "page %d of document %s", exc, page_number, document_id
            )
            facts.extend(_rule_fallback(document_id, [page]))

    return facts


def _rule_fallback(document_id: int, pages: list[dict]) -> list[dict]:
    from app.services.normalizer import facts_from_pages as _rules

    return _rules(document_id, pages)


def sanitize_fact(fact: dict[str, Any], document_id: int) -> dict[str, Any] | None:
    """Standalone guard used by tests/manual paths to harden a fact dict."""
    try:
        item = _LlmFact(**fact)
    except Exception:
        return None
    coerced = _coerce_facts(
        _LlmFactBatch(facts=[item]), document_id, item.page_number or 1
    )
    return coerced[0] if coerced else None