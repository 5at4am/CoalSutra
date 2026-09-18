"""Normalize extracted pages into `ExtractedFact` rows (rule-based).

Home of the **normalize** pipeline stage in CLAUDE.md. The contracts are fixed
upstream (models/schemas/migrations already exist); this module fills the gap:
turning per-page `{text, tables}` records into flat facts of the shape
`entity, value, unit, date_reference, page, raw_snippet, confidence`.

The rules are tuned to coal/geology survey language (CMPDI/CIL material):
- text scanning matches a known unit immediately after a number, requires a
  known domain entity in the same sentence (precision over recall), attaches
  any year in the sentence as `date_reference`, and marks unit-less figures
  (ratios) only when the entity is ratio-like.
- table scanning maps headers to `(entity, unit)` and attaches the row year.
  Char/id and date columns are skipped so ``block``, ``ratio_year`` etc. never
  become facts.

Confidence is a deterministic heuristic (0.98 tables, 0.9 text+unit, 0.8
unit-less ratio) that the **validate** stage and review gate can later use to
decide what needs a human look. An LLM assistant may replace the rules later
without changing the produced shape.
"""

from __future__ import annotations

import re
from datetime import date

NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_:/])\d[\d,]*\.?\d*")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

# (regex matched right after a number, canonical unit label). Longest/most
# specific first; `match()` is anchored at the start of the tail so only the
# first pattern that fits at that position can win.
UNITS: list[tuple[str, str]] = [
    (r"million\s+tonnes", "MT"),
    (r"million\s+tons", "MT"),
    (r"mtpa", "MTPA"),
    (r"mt/yr", "MT/yr"),
    (r"mt\b", "MT"),
    (r"cubic\s+metres?", "m³"),
    (r"cum", "m³"),
    (r"m3", "m³"),
    (r"hectares?", "ha"),
    (r"square\s+kilometres?|sq\.?\s*km", "km²"),
    (r"kilometres|kilometers", "km"),
    (r"per\s+cent|percent", "%"),
    (r"crores?", "INR crore"),
    (r"lakhs?", "INR lakh"),
    (r"tonnes|tons|tonne|ton\b", "t"),
    (r"mm", "mm"),
    (r"%", "%"),
    (r"m\b", "m"),
    (r"t\b", "t"),
]
_UNIT_PATTERNS = [(re.compile(p, re.IGNORECASE), label) for p, label in UNITS]

# (regex over a sentence/a table header, canonical entity, is_unitless_ratio)
DOMAIN_ENTITIES: list[tuple[re.Pattern[str], str, bool]] = [
    (
        re.compile(r"overburden\s+ratio|stripping\s+ratio|\bob\s+ratio\b|\bstrip\s+ratio\b", re.I),
        "overburden_ratio",
        True,
    ),
    (re.compile(r"wash\s+yield", re.I), "wash_yield", True),
    (
        re.compile(r"geological\s+reserve|proved\s+reserve|total\s+reserve|coal\s+reserve|\breserve\b", re.I),
        "coal_reserve",
        False,
    ),
    (re.compile(r"ash\s+content|inherent\s+ash|\bash\b", re.I), "ash_content", False),
    (re.compile(r"moisture\s+content|\bmoisture\b", re.I), "moisture", False),
    (re.compile(r"coal\s+production|\bproduction\b|despatch", re.I), "production", False),
    (re.compile(r"installed\s+capacity|\bcapacity\b", re.I), "capacity", False),
]

# (regex over a table header, (entity, unit)). `reserve_mt`-style headers hit
# the reserve rule; ratio columns named `*_year` are excluded by the date check
# before resolution so year-valued cells never become ratio facts.
HEADER_FACTS: list[tuple[re.Pattern[str], tuple[str, str | None]]] = [
    (re.compile(r"reserve", re.I), ("coal_reserve", "MT")),
    (re.compile(r"overburden|stripping|strip\s+ratio", re.I), ("overburden_ratio", None)),
    (re.compile(r"wash\s+yield", re.I), ("wash_yield", None)),
    (re.compile(r"ash", re.I), ("ash_content", "%")),
    (re.compile(r"moisture", re.I), ("moisture", "%")),
    (re.compile(r"production|despatch|output", re.I), ("production", "t")),
    (re.compile(r"capacity", re.I), ("capacity", "t")),
]

# Fallback when a header is not in HEADER_FACTS: strip a unit suffix and treat
# the rest of the header as a plain entity label.
UNIT_SUFFIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:_|^)mtpa$", re.I), "MTPA"),
    (re.compile(r"(?:_|^)mt$|(?:_|^)(?:tonnes?|tons?)$", re.I), "MT"),
    (re.compile(r"(?:_|^)mm$", re.I), "mm"),
    (re.compile(r"(?:_|^)pct$|(?:_|^)percent$", re.I), "%"),
    (re.compile(r"(?:_|^)ha$", re.I), "ha"),
]

CONFIDENCE_TABLE = 0.98
CONFIDENCE_TEXT_UNIT = 0.9
CONFIDENCE_RATIO = 0.8


def _clean_number(raw: str) -> str:
    return raw.replace(",", "")


def _is_year(value: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}", value))


def _year_to_date(value: str) -> date:
    return date(int(value), 1, 1)


def _match_unit(text: str, num_end: int) -> str | None:
    tail = text[num_end:].lstrip()
    for pattern, label in _UNIT_PATTERNS:
        if pattern.match(tail):
            return label
    return None


def _domain_entity(sentence: str) -> tuple[str, bool] | None:
    for pattern, entity, unitless in DOMAIN_ENTITIES:
        if pattern.search(sentence):
            return entity, unitless
    return None


def _facts_from_sentence(sentence: str, page_number: int) -> list[dict]:
    matched = _domain_entity(sentence)
    if matched is None:
        return []
    entity, unitless_ratio = matched

    year_match = YEAR_RE.search(sentence)
    date_ref = _year_to_date(year_match.group(1)) if year_match else None

    facts = []
    for num_match in NUMBER_RE.finditer(sentence):
        raw = _clean_number(num_match.group())
        value = raw.rstrip(".")  # sentence punctuation vs decimal point
        if _is_year(value):
            continue
        unit = _match_unit(sentence, num_match.end())
        if unit is None and not unitless_ratio:
            continue
        facts.append(
            {
                "entity": entity,
                "value": value,
                "unit": unit,
                "date_reference": date_ref,
                "page_number": page_number,
                "raw_snippet": sentence.strip(),
                "confidence": CONFIDENCE_TEXT_UNIT if unit else CONFIDENCE_RATIO,
            }
        )
    return facts


def _is_date_column(header: str) -> bool:
    return bool(re.search(r"year|fiscal|date", header, re.I))


def _resolve_header(header: str) -> tuple[str, str | None] | None:
    if _is_date_column(header):
        return None
    for pattern, resolved in HEADER_FACTS:
        if pattern.search(header):
            return resolved
    for pattern, unit in UNIT_SUFFIXES:
        if pattern.search(header):
            entity = pattern.sub("", header).strip(" _-")
            if entity:
                return entity.replace("_", " "), unit
    return None


def _row_year(row: list[str]) -> int | None:
    for cell in row:
        cell = str(cell).strip()
        if _is_year(cell):
            return int(cell)
    return None


def _facts_from_table(table: list[list[object]], page_number: int) -> list[dict]:
    if not table or not table[0]:
        return []
    headers = [str(h).strip() for h in table[0]]
    columns = []
    for idx, header in enumerate(headers):
        resolved = _resolve_header(header.lower())
        if resolved is not None:
            columns.append((idx, resolved[0], resolved[1]))

    facts = []
    for row in table[1:]:
        if len(row) < len(headers):
            continue
        row_year = _row_year(list(map(str, row)))
        date_ref = date(row_year, 1, 1) if row_year else None
        for idx, entity, unit in columns:
            cell = str(row[idx]).strip()
            if not cell or _is_year(cell) or not NUMBER_RE.fullmatch(cell.replace(",", "")):
                continue
            facts.append(
                {
                    "entity": entity,
                    "value": _clean_number(cell),
                    "unit": unit,
                    "date_reference": date_ref,
                    "page_number": page_number,
                    "raw_snippet": "; ".join(
                        f"{headers[j]}={row[j]}" for j in range(min(len(headers), len(row)))
                    ),
                    "confidence": CONFIDENCE_TABLE,
                }
            )
    return facts


def facts_from_pages(document_id: int, pages: list[dict]) -> list[dict]:
    """Flatten extracted pages into normalized fact dicts for one document."""
    facts = []
    for page in pages:
        page_number = page.get("page_number", 1)
        text = page.get("text") or ""
        for line in re.split(r"\n+", text):
            for sentence in re.split(r"(?<=[.!?])\s+", line.strip()):
                facts.extend(_facts_from_sentence(sentence, page_number))
        for table in page.get("tables") or []:
            facts.extend(_facts_from_table(table, page_number))

    normalized = []
    for fact in facts:
        fact = dict(fact)
        fact["document_id"] = document_id
        normalized.append(fact)
    return normalized