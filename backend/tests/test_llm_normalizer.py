"""Tests for the LLM normalizer: extraction, fallback, and sanitization.

The real provider is never called — `llm` is injected, so these tests run
offline and deterministically. The rule-based fallback path is also exercised
to guarantee the pipeline works with an empty/absent LLM_API_KEY.
"""

from datetime import date

import pytest

from app.core.llm import LLMDisabledError, LLMError
from app.services.normalization.normalizer import (
    facts_from_pages,
    _LlmFactBatch,
)


def _fake_llm(facts_dicts):
    def _llm(prompt, schema):
        return schema.model_validate({"facts": facts_dicts})

    return _llm


def test_extracts_facts_via_llm():
    llm = _fake_llm(
        [
            {
                "entity": "proved_reserve",
                "value": "1240",
                "unit": "MT",
                "date_reference": "2019-01-01",
                "page_number": 99,
                "raw_snippet": "Proved reserve of the block is 1,240 MT.",
                "confidence": 0.95,
            }
        ]
    )
    pages = [
        {
            "page_number": 2,
            "text": "Proved reserve of the block is 1,240 MT.",
            "tables": [],
        }
    ]

    facts = facts_from_pages(1, pages, llm=llm)

    assert len(facts) == 1
    fact = facts[0]
    assert fact["document_id"] == 1
    assert fact["page_number"] == 2  # pinned to the page, not the LLM's guess
    assert fact["entity"] == "proved_reserve"
    assert fact["value"] == "1240"
    assert fact["unit"] == "MT"
    assert fact["date_reference"] == date(2019, 1, 1)


def test_snippet_and_entity_normalization():
    llm = _fake_llm(
        [
            {
                "entity": "Coal Reserve",
                "value": 1240,
                "unit": "MT",
                "date_reference": None,
                "page_number": 1,
                "raw_snippet": "  Total reserve estimate of 1,240 MT.  ",
                "confidence": 0.9,
            }
        ]
    )
    facts = facts_from_pages(1, [{"page_number": 1, "text": "Total reserve estimate of 1,240 MT."}], llm=llm)

    entity, snippet = facts[0]["entity"], facts[0]["raw_snippet"]
    assert entity == "coal_reserve"
    assert snippet == "Total reserve estimate of 1,240 MT."  # whitespace trimmed, verbatim kept


def test_year_and_full_date_parsing():
    llm = _fake_llm(
        [
            {
                "entity": "coal_reserve",
                "value": "900",
                "unit": "MT",
                "date_reference": "2023",
                "page_number": 1,
                "raw_snippet": "As of 2023 reserve was 900 MT.",
                "confidence": 0.9,
            }
        ]
    )
    facts = facts_from_pages(1, [{"page_number": 1, "text": "As of 2023 reserve was 900 MT."}], llm=llm)
    assert facts[0]["date_reference"] == date(2023, 1, 1)


def test_confidence_is_clamped():
    llm = _fake_llm(
        [
            {
                "entity": "coal_reserve",
                "value": "900",
                "unit": "MT",
                "date_reference": None,
                "page_number": 1,
                "raw_snippet": "reserve 900 MT",
                "confidence": 1.4,
            },
            {
                "entity": "coal_reserve",
                "value": "901",
                "unit": "MT",
                "date_reference": None,
                "page_number": 1,
                "raw_snippet": "reserve 901 MT",
                "confidence": -0.2,
            },
        ]
    )
    facts = facts_from_pages(1, [{"page_number": 1, "text": "x", "tables": []}], llm=llm)
    assert facts[0]["confidence"] == 1.0
    assert facts[1]["confidence"] == 0.0


def test_blank_snippet_fact_dropped():
    llm = _fake_llm(
        [
            {
                "entity": "coal_reserve",
                "value": "900",
                "unit": "MT",
                "date_reference": None,
                "page_number": 1,
                "raw_snippet": "   ",
                "confidence": 0.9,
            }
        ]
    )
    facts = facts_from_pages(1, [{"page_number": 1, "text": "x", "tables": []}], llm=llm)
    assert facts == []


def test_empty_text_pages_skipped():
    llm = _fake_llm(
        [
            {
                "entity": "coal_reserve",
                "value": "900",
                "unit": "MT",
                "date_reference": None,
                "page_number": 1,
                "raw_snippet": "reserve 900 MT",
                "confidence": 0.9,
            }
        ]
    )
    pages = [{"page_number": 1, "text": "", "tables": []}]
    facts = facts_from_pages(1, pages, llm=llm)
    assert facts == []


def test_fallback_to_rules_when_llm_disabled():
    def _disabled(prompt, schema):
        raise LLMDisabledError("LLM_API_KEY not set")

    pages = [
        {
            "page_number": 1,
            "text": "Total reserve estimate of 1,240 MT for the Bhubaneshwari block.",
            "tables": [],
        }
    ]
    facts = facts_from_pages(1, pages, llm=_disabled)

    assert any(
        f["entity"] == "coal_reserve" and f["value"] == "1240" and f["unit"] == "MT"
        for f in facts
    )


def test_fallback_to_rules_on_provider_error():
    def _boom(prompt, schema):
        raise LLMError("provider 500")

    pages = [
        {
            "page_number": 1,
            "text": "Overburden ratio reported at 2.1 in the Q3 survey.",
            "tables": [],
        }
    ]
    facts = facts_from_pages(1, pages, llm=_boom)

    assert any(f["entity"] == "overburden_ratio" and f["value"] == "2.1" for f in facts)


def test_per_page_fallback_keeps_earlier_pages():
    def _llm_second_page_fails(prompt, schema):
        if "PAGE NUMBER: 1" in prompt:
            return schema.model_validate(
                {
                    "facts": [
                        {
                            "entity": "coal_reserve",
                            "value": "900",
                            "unit": "MT",
                            "date_reference": None,
                            "page_number": 1,
                            "raw_snippet": "reserve 900 MT",
                            "confidence": 0.9,
                        }
                    ]
                }
            )
        raise LLMError("page 2 failed")

    pages = [
        {"page_number": 1, "text": "reserve 900 MT", "tables": []},
        {
            "page_number": 2,
            "text": "Overburden ratio reported at 2.1 in the Q3 survey.",
            "tables": [],
        },
    ]
    facts = facts_from_pages(1, pages, llm=_llm_second_page_fails)

    values = {(f["entity"], f["value"], f["page_number"]) for f in facts}
    assert ("coal_reserve", "900", 1) in values
    assert ("overburden_ratio", "2.1", 2) in values