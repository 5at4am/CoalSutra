"""Unit tests for the rule-based normalizer (normalize stage)."""

from datetime import date

from app.services.normalizer import (
    CONFIDENCE_RATIO,
    CONFIDENCE_TABLE,
    CONFIDENCE_TEXT_UNIT,
    facts_from_pages,
)


def _first_fact(pages):
    facts = facts_from_pages(1, pages)
    assert len(facts) == 1
    return facts[0]


def test_text_number_with_unit():
    fact = _first_fact(
        [{"page_number": 3, "text": "Proved reserve of the block is 1,240 MT.", "tables": []}]
    )
    assert fact["entity"] == "coal_reserve"
    assert fact["value"] == "1240"
    assert fact["unit"] == "MT"
    assert fact["page_number"] == 3
    assert fact["confidence"] == CONFIDENCE_TEXT_UNIT


def test_text_year_becomes_date_reference():
    fact = _first_fact(
        [{"page_number": 1, "text": "As of March 2023, total reserve was 900 MT.", "tables": []}]
    )
    assert fact["date_reference"] == date(2023, 1, 1)


def test_unitless_ratio_gets_fact_but_no_unit():
    fact = _first_fact(
        [{"page_number": 1, "text": "Overburden ratio reported at 2.1 in the survey.", "tables": []}]
    )
    assert fact["entity"] == "overburden_ratio"
    assert fact["value"] == "2.1"
    assert fact["unit"] is None
    assert fact["confidence"] == CONFIDENCE_RATIO


def test_no_fact_without_domain_entity():
    pages = [{"page_number": 1, "text": "The pipeline cost 500 crore Rs last year.", "tables": []}]
    assert facts_from_pages(1, pages) == []


def test_quarter_number_is_not_a_fact():
    pages = [
        {"page_number": 1, "text": "Overburden ratio in Q3 2024 was 1.9:1.", "tables": []}
    ]
    facts = facts_from_pages(1, pages)
    values = [f["value"] for f in facts]
    assert "3" not in values
    assert "2024" not in values
    assert values == ["1.9"]


def test_table_facts_with_row_year_and_citation():
    table = [
        ["block", "reserve_mt", "ratio_year"],
        ["Bhubaneshwari", "1240", "2019"],
        ["Kusunda", "938", "2019"],
    ]
    facts = facts_from_pages(1, [{"page_number": 2, "text": "", "tables": [table]}])

    assert len(facts) == 2
    assert all(f["entity"] == "coal_reserve" and f["unit"] == "MT" for f in facts)
    assert all(f["confidence"] == CONFIDENCE_TABLE for f in facts)
    assert all(f["date_reference"] == date(2019, 1, 1) for f in facts)
    assert facts[0]["value"] == "1240"
    assert "block=Bhubaneshwari" in facts[0]["raw_snippet"]


def test_char_and_date_columns_are_skipped():
    table = [
        ["block", "ratio_year", "reserve_mt"],
        ["Jitpur", "2019", "500"],
    ]
    facts = facts_from_pages(1, [{"page_number": 1, "text": "", "tables": [table]}])
    assert len(facts) == 1
    assert facts[0]["entity"] == "coal_reserve"
    assert facts[0]["value"] == "500"


def test_unit_suffix_header_fallback():
    table = [["block", "sale_mt"], ["Mine A", "27000000"]]
    facts = facts_from_pages(1, [{"page_number": 1, "text": "", "tables": [table]}])
    assert len(facts) == 1
    assert facts[0]["entity"] == "sale"
    assert facts[0]["unit"] == "MT"


def test_non_offset_header_skipped():
    table = [["block", "latitude"], ["Mine A", "23.7"]]
    assert facts_from_pages(1, [{"page_number": 1, "text": "", "tables": [table]}]) == []