"""Cross-source conflict detection for extracted facts (validate stage).

Runs after new `ExtractedFact` rows are saved. Two facts conflict when they
describe the SAME entity at an OVERLAPPING date but with a DIFFERENT value AND
come from DIFFERENT documents. A conflicting pair is never silently overwritten
— it becomes an `open` `ConflictFlag` for the human-in-the-loop review queue.

The comparison is pure Python over facts in memory so it is trivially testable
without any LLM or network.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models import ConflictFlag, ExtractedFact
from app.models.enums import ConflictStatus

logger = logging.getLogger(__name__)


def _overlap_year(fact_a: ExtractedFact, fact_b: ExtractedFact) -> int | None:
    """Return the shared year when both facts carry an overlapping date_reference."""
    if fact_a.date_reference is None or fact_b.date_reference is None:
        return None
    if fact_a.date_reference.year != fact_b.date_reference.year:
        return None
    return fact_a.date_reference.year


def _value_key(value: str) -> tuple[str, object]:
    """Normalize a value for comparison so '1,240' == '1240'."""
    value = value.strip()
    try:
        return ("number", float(value.replace(",", "")))
    except ValueError:
        return ("string", value)


def _existing_pairs(session: Session) -> set[frozenset[int]]:
    return {
        frozenset((flag.fact_a_id, flag.fact_b_id)) for flag in session.query(ConflictFlag)
    }


def flag_conflicts(
    session: Session, document_id: int | None = None
) -> list[ConflictFlag]:
    """Scan stored facts and create `open` ConflictFlag rows for value conflicts.

    Comparison always spans ALL documents (a stored figure from an older
    document is what a new one can collide with); ``document_id`` is kept as the
    caller's label of *why* validation ran. Idempotent: an already-flagged pair
    is never re-flagged.
    """
    facts = session.query(ExtractedFact).all()

    groups: dict[tuple[str, int], list[ExtractedFact]] = {}
    for fact in facts:
        if fact.date_reference is None:
            continue
        groups.setdefault((fact.entity, fact.date_reference.year), []).append(fact)

    existing = _existing_pairs(session)
    created: list[ConflictFlag] = []

    for (entity, year), members in groups.items():
        if len(members) < 2:
            continue
        # Baseline = the earliest-known fact for this (entity, year).
        baseline = min(members, key=lambda f: f.id)
        for other in sorted(members, key=lambda f: f.id):
            if other.id == baseline.id or other.document_id == baseline.document_id:
                continue
            if _value_key(baseline.value) == _value_key(other.value):
                continue
            pair = frozenset((baseline.id, other.id))
            if pair in existing:
                continue

            fact_a, fact_b = baseline, other
            flag = ConflictFlag(
                fact_a_id=fact_a.id,
                fact_b_id=fact_b.id,
                reason=(
                    f"'{entity}' for {year} reported as {fact_a.value}"
                    f"{f' {fact_a.unit}' if fact_a.unit else ''} (doc {fact_a.document_id}) "
                    f"vs {fact_b.value}{f' {fact_b.unit}' if fact_b.unit else ''} "
                    f"(doc {fact_b.document_id})"
                ),
                status=ConflictStatus.open,
            )
            session.add(flag)
            session.flush()
            created.append(flag)
            existing.add(pair)
            logger.warning(
                "validator: conflict flagged for '%s' (%d): doc %s = %s vs doc %s = %s",
                entity,
                year,
                fact_a.document_id,
                fact_a.value,
                fact_b.document_id,
                fact_b.value,
            )

    return created