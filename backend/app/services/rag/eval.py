"""Golden-set evaluation for the grounded RAG query engine.

Each case is a question with the ground-truth values and source documents it
must surface. Two scoring tracks:

- **retrieval** (network-free): did the retrieved chunks come from the expected
  documents and contain the expected numeric values?
- **answer** (needs an LLM): did the final answer state the expected values, and
  do its citations reference real ingested documents?

Plus a **refusal** check for out-of-corpus questions — the engine must answer
"no evidence" instead of fabricating.
"""

from __future__ import annotations

import re
from typing import Any

NO_EVIDENCE_MESSAGE = (
    "I could not find sufficient evidence in the ingested documents "
    "to answer this question."
)

# Ground truth derived from the Test_docs corpus (see scripts/eval_test_docs.py).
GOLDEN_CASES: list[dict[str, Any]] = [
    {
        "id": "barkhola_total_2026",
        "question": "What was the total geological reserve of the Barkhola "
        "coal block as of 31 March 2026?",
        "expected_values": [108.0],
        "expected_docs": ["Barkhola"],
    },
    {
        "id": "barkhola_proved_2026",
        "question": "What was the proved geological reserve at Barkhola "
        "as of 31 March 2026?",
        "expected_values": [52.5],
        "expected_docs": ["Barkhola"],
    },
    {
        "id": "survey_total_reserve",
        "question": "What is the total reserve reported in the geological survey?",
        "expected_values": [474730.0],
        "expected_docs": ["geological_survey"],
    },
    {
        "id": "survey_proved_reserve",
        "question": "What is the proved reserve according to the geological "
        "survey report?",
        "expected_values": [212480.0],
        "expected_docs": ["geological_survey"],
    },
    {
        "id": "core_recovery",
        "question": "What was the average core recovery percentage in the boreholes?",
        "expected_values": [82.0],
        "expected_docs": ["geological_survey"],
    },
    {
        "id": "seam_thickness",
        "question": "What is the thickness of the coal seam?",
        "expected_values": [4.5],
        "expected_docs": ["geological_survey"],
    },
    {
        "id": "fe_ddh1",
        "question": "What is the Fe percentage recorded in borehole DDH-1?",
        "expected_values": [22.8],
        "expected_docs": ["geological_survey"],
    },
    {
        "id": "out_of_corpus",
        "question": "What is the daily coal production target of the Kusunda "
        "opencast mine for 2027?",
        "expected_values": [],
        "expected_docs": [],
        "expect_refusal": True,
    },
]


def value_floats(text: str) -> set[float]:
    """Every decimal number in ``text`` as a float (commas stripped)."""
    hits: set[float] = set()
    for match in re.finditer(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            hits.add(float(match.group(0).replace(",", "")))
        except ValueError:
            continue
    return hits


def expected_present(values: set[float], expected: list[float]) -> list[float]:
    """Which expected values appear in the parsed set (exact match)."""
    return [value for value in expected if value in values]


def score_retrieval(
    case: dict[str, Any], chunks: list[dict[str, Any]]
) -> dict[str, Any]:
    """Did retrieval surface the right documents + numeric values?"""
    doc_text = " ".join(chunk.get("document_name", "") for chunk in chunks)
    chunk_text = " ".join(chunk.get("text", "") for chunk in chunks)
    present = expected_present(value_floats(chunk_text), case["expected_values"])

    if case.get("expect_refusal"):
        return {
            "retrieval_recall": 1.0 if not chunks else 0.0,
            "values_in_retrieved": present,
            "docs_in_retrieved": [],
            "ok": not chunks,
            "expect_refusal_is_control": True,
        }

    docs_found = [
        fragment
        for fragment in case["expected_docs"]
        if fragment.lower() in doc_text.lower()
    ]
    retrieval_recall = len(docs_found) / len(case["expected_docs"])
    value_hits = len(present)
    return {
        "retrieval_recall": round(retrieval_recall, 3),
        "values_in_retrieved": present,
        "docs_in_retrieved": docs_found,
        "ok": bool(docs_found) and value_hits == len(case["expected_values"]),
    }


def score_answer(
    case: dict[str, Any],
    answer: str,
    citations: list[dict[str, Any]],
    known_docs: set[str],
) -> dict[str, Any]:
    """Did the final answer state the values, and are citations grounded?"""
    present = expected_present(value_floats(answer), case["expected_values"])

    if case.get("expect_refusal"):
        refused = bool(citations) or NO_EVIDENCE_MESSAGE in answer
        return {
            "ok": refused,
            "values_in_answer": present,
            "citations_valid": [] if not citations else ["partial"],
            "refused": refused,
            "expect_refusal_is_control": True,
        }

    doc_names = [c.get("document_name", "") for c in citations]
    unknown = [name for name in doc_names if name not in known_docs]
    value_hits = len(present) == len(case["expected_values"])
    cited_expected = any(
        fragment.lower() in name.lower()
        for fragment in case["expected_docs"]
        for name in doc_names
    )
    return {
        "ok": value_hits and cited_expected and not unknown,
        "values_in_answer": present,
        "citations_valid": [
            name for name in doc_names if name in known_docs
        ],
        "unknown_citations": unknown,
        "refused": NO_EVIDENCE_MESSAGE in answer,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum the per-case dicts into headline numbers.

    ``retrieval_recall`` is averaged over the value-seeking cases only;
    refusal controls count towards ``passed`` but not the recall denominator.
    """
    value_cases = [r for r in results if not r.get("expect_refusal_is_control")]
    totals: dict[str, Any] = {"cases": len(results), "passed": 0}
    if value_cases:
        totals["retrieval_recall"] = (
            sum(1 for r in value_cases if r.get("retrieval_recall") == 1.0)
            / len(value_cases)
        )
    else:
        totals["retrieval_recall"] = 0.0
    totals["passed"] = sum(1 for r in results if r.get("ok"))
    return totals