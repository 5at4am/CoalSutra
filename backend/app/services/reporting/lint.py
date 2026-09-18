"""Facts-check lint for drafted report sections.

Deterministic validation gate that runs AFTER the LLM has drafted a section and
before a report is approved:

- every number printed in a section body must exist (within tolerance) among the
  in-scope fact values;
- every figure that matches a fact value must be cited in that section;
- numbers that match *none* of the facts are classified: years, percentages,
  counts/ordinals, dates, and figures queued by the facts themselves (differences
  and sums of two in-scope values of the same entity) are treated as benign;
  anything else is an **error** — a likely fabricated figure.

This turns LLM nondeterminism into a testable, reviewable gate.
"""

from __future__ import annotations

import itertools
import re
from typing import Any

_NUMBER_RE = re.compile(r"[+-]?\d[\d,]*(?:\.\d+)?%?")
_DATE_MASK_RE = re.compile(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b")
_YEAR_BOUNDS = (1900, 2100)
_SMALL_INT = 12
_COUNT_WORDS = {
    "rows",
    "pages",
    "facts",
    "documents",
    "sources",
    "sections",
    "entries",
    "items",
    "charts",
    "figures",
    "tables",
    "quarters",
    "months",
    "days",
    "weeks",
}


def _parse_number(token: str) -> tuple[float, bool] | None:
    """Return (value, is_percentage) for a token like '38.5', '9,480' or '6.8%'."""
    stripped = token.strip().rstrip("%").replace(",", "")
    try:
        value = float(stripped)
    except ValueError:
        return None
    return value, token.strip().endswith("%")


def _numeric_facts(facts: list[dict[str, Any]]) -> list[tuple[float, int, str]]:
    """(value, fact_id, entity) for every numeric in-scope fact."""
    rows: list[tuple[float, int, str]] = []
    for fact in facts:
        try:
            value = float(str(fact["value"]).replace(",", ""))
        except (TypeError, ValueError):
            continue
        rows.append((round(value, 6), fact["fact_id"], fact.get("entity") or ""))
    return rows


def _facts_for_value(
    numeric: list[tuple[float, int, str]], number: float
) -> list[int]:
    return [fact_id for value, fact_id, _ in numeric if abs(value - number) < 1e-6]


def _derived_values(numeric: list[tuple[float, int, str]]) -> dict[float, list[str]]:
    """Magnitudes the facts themselves imply: same-entity diffs and pair sums."""
    derived: dict[float, list[str]] = {}
    for (a_value, _a_id, a_entity), (b_value, _b_id, b_entity) in itertools.combinations(
        numeric, 2
    ):
        if a_entity == b_entity:
            delta = round(abs(a_value - b_value), 6)
            derived.setdefault(delta, []).append(f"difference {a_entity}")
            total = round(a_value + b_value, 6)
            derived.setdefault(total, []).append(f"sum {a_entity}")
    return derived


def lint_sections(
    sections: dict[str, dict[str, Any]],
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate figures in every drafted section against the in-scope facts.

    Returns ``{ok, summary, issues}``; ``ok`` is False whenever any section
    contains a figure that matches no fact value and is not explained as a
    year / percentage / ordinal / count / date / derived magnitude.
    """
    numeric = _numeric_facts(facts)
    derived = _derived_values(numeric)
    issues: list[dict[str, Any]] = []
    checked = 0
    matched = 0

    for key, draft in sections.items():
        if draft.get("automatic"):
            continue
        body = _DATE_MASK_RE.sub(" ", draft.get("body") or "")
        cited_ids = {
            citation.get("fact_id")
            for citation in draft.get("citations") or []
            if citation.get("fact_id") is not None
        }
        for match in _NUMBER_RE.finditer(body):
            token = match.group(0)
            parsed = _parse_number(token)
            if parsed is None:
                continue
            number, is_percentage = parsed
            checked += 1
            context = body[max(0, match.start() - 30) : match.end() + 30].replace(
                "\n", " "
            )

            fact_ids = _facts_for_value(numeric, number)
            if fact_ids:
                matched += 1
                if not any(fid in cited_ids for fid in fact_ids):
                    issues.append(
                        {
                            "severity": "error",
                            "section": key,
                            "number": token,
                            "context": context,
                            "reason": "figure matches an in-scope fact value but "
                            "the section does not cite that fact",
                        }
                    )
                continue

            # Benign classes of unmatched numbers.
            if is_percentage:
                _issue(issues, "info", key, token, context,
                       "percentage figure not tied to an in-scope fact value")
                continue
            if number.is_integer() and _YEAR_BOUNDS[0] <= number <= _YEAR_BOUNDS[1]:
                continue
            if _COUNT_WORDS.intersection(
                (body[match.end() : match.end() + 20]).lstrip().lower().split()
            ):
                continue
            if number.is_integer() and abs(number) <= _SMALL_INT:
                continue
            derived_hits = [d for d, _reasons in derived.items() if abs(d - abs(number)) < 1e-6]
            if derived_hits:
                _issue(issues, "info", key, token, context,
                       "derived figure consistent with the facts (difference/sum)")
                continue

            _issue(issues, "error", key, token, context,
                   "figure matches no in-scope fact value and is not a derived "
                   "magnitude — likely fabricated")

    severities: dict[str, int] = {}
    for issue in issues:
        severity = issue["severity"]
        severities[severity] = severities.get(severity, 0) + 1
    result = {
        "ok": not severities.get("error", 0),
        "summary": {
            "figures_checked": checked,
            "figures_matched_to_facts": matched,
            "errors": severities.get("error", 0),
            "warnings": severities.get("warning", 0),
            "infos": severities.get("info", 0),
        },
        "issues": issues,
    }
    return result


def _issue(
    issues: list[dict[str, Any]],
    severity: str,
    section: str,
    number: str,
    context: str,
    reason: str,
) -> None:
    issues.append(
        {
            "severity": severity,
            "section": section,
            "number": number,
            "context": context,
            "reason": reason,
        }
    )