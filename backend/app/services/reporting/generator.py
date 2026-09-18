"""Report generation: draft every template section from validated facts.

The same citation discipline as the query engine (Stage 4) applies here: the
LLM is handed a bounded set of facts (with ids) and chunks and is required to
cite every figure it prints back to a source `ExtractedFact` + page. Citations
that reference unknown fact ids are dropped, so fabricated references cannot
creep into a report. The result is saved as a `Report` row with status=draft.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.llm import LLMError, call_llm
from app.models import Document, DocumentChunk, ExtractedFact, Report
from app.models.enums import ReportStatus
from app.services.reporting.templates import get_template

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHUNKS = 12
MAX_FACTS_PER_SECTION = 60


class SectionCitation(BaseModel):
    fact_id: int | None = None
    document_name: str | None = None
    page_number: int | None = None


class SectionDraft(BaseModel):
    body: str
    citations: list[SectionCitation] = []


def generate_report(
    session: Session,
    template_type: str,
    filters: dict[str, Any] | None = None,
    llm: Callable[[str, type[BaseModel]], BaseModel] | None = None,
    title: str | None = None,
) -> Report:
    """Generate a draft report for ``template_type`` over filtered facts.

    ``filters`` supports: ``title``, ``entity``/``entities``, ``document_id``/
    ``document_ids``, ``date_from``/``date_to`` (date or 'YYYY-MM-DD').
    ``llm`` defaults to the real provider, resolved at call time (monkeypatchable).
    """
    template = get_template(template_type)
    llm_fn = llm or call_llm
    filters = filters or {}

    facts = pull_facts(session, filters)
    fact_index = {fact["fact_id"]: fact for fact in facts}
    chunks = pull_chunks(session, filters)

    sections_out: dict[str, dict[str, Any]] = {}
    all_citations: list[dict[str, Any]] = []
    for section in template["sections"]:
        if section.get("automatic"):
            sections_out[section["key"]] = {
                "title": section["title"],
                "body": _sources_body(all_citations),
                "citations": [dict(c) for c in all_citations],
                "automatic": True,
            }
            continue

        limited_facts = facts[:MAX_FACTS_PER_SECTION]
        prompt = _section_prompt(section, template, limited_facts, chunks)
        try:
            draft = llm_fn(prompt, SectionDraft)
            body = draft.body
            citations = []
            for citation in draft.citations:
                normalized = _normalize_citation(citation, fact_index)
                if normalized:
                    citations.append(normalized)
        except LLMError as exc:
            logger.warning(
                "generator: LLM unavailable for '%s' section; "
                "using fact-only fallback: %s",
                section["key"],
                exc,
            )
            body = _fallback_body(limited_facts)
            citations = [_citation_from_fact(fact) for fact in limited_facts]
        sections_out[section["key"]] = {
            "title": section["title"],
            "body": body,
            "citations": citations,
        }
        all_citations.extend(citations)
        logger.info(
            "generator: '%s' section drafted with %d validated citation(s)",
            section["key"],
            len(citations),
        )

    report = Report(
        title=title or template["title"],
        template_type=template_type,
        status=ReportStatus.draft,
        content={
            "sections": sections_out,
            "template": template.get("description", ""),
            "facts": facts,
            "scope": _scope_filter(filters),
        },
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    logger.info(
        "generator: saved draft report %s (%s, %d facts in scope)",
        report.id,
        template_type,
        len(facts),
    )
    return report


def pull_facts(session: Session, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Facts matching the report filter, joined to their source document name."""
    query = (
        session.query(ExtractedFact, Document.filename)
        .join(Document, ExtractedFact.document_id == Document.id)
    )

    entities = filters.get("entities") or (
        [filters["entity"]] if filters.get("entity") else None
    )
    if entities:
        query = query.filter(ExtractedFact.entity.in_(entities))
    document_ids = filters.get("document_ids") or (
        [filters["document_id"]] if filters.get("document_id") else None
    )
    if document_ids:
        query = query.filter(ExtractedFact.document_id.in_(document_ids))
    if filters.get("date_from"):
        query = query.filter(ExtractedFact.date_reference >= _as_date(filters["date_from"]))
    if filters.get("date_to"):
        query = query.filter(ExtractedFact.date_reference <= _as_date(filters["date_to"]))

    rows = query.order_by(ExtractedFact.id.asc()).all()
    return [
        {
            "fact_id": fact.id,
            "entity": fact.entity,
            "value": fact.value,
            "unit": fact.unit,
            "date_reference": fact.date_reference.isoformat() if fact.date_reference else None,
            "document_name": filename,
            "page_number": fact.page_number,
            "raw_snippet": fact.raw_snippet,
            "confidence": fact.confidence,
        }
        for fact, filename in rows
    ]


def pull_chunks(session: Session, filters: dict[str, Any]) -> list[dict[str, Any]]:
    query = (
        session.query(DocumentChunk, Document.filename)
        .join(Document, DocumentChunk.document_id == Document.id)
    )
    document_ids = filters.get("document_ids") or (
        [filters["document_id"]] if filters.get("document_id") else None
    )
    if document_ids:
        query = query.filter(DocumentChunk.document_id.in_(document_ids))
    rows = query.order_by(DocumentChunk.id.desc()).limit(40).all()
    return [
        {
            "chunk_id": chunk.id,
            "document_name": filename,
            "page_number": chunk.page_number,
            "text": chunk.text,
        }
        for chunk, filename in rows
    ]


# --- prompt / validation helpers ------------------------------------------


def _section_prompt(
    section: dict, template: dict, facts: list[dict], chunks: list[dict]
) -> str:
    dated = [f["date_reference"] for f in facts if f.get("date_reference")]
    coverage = (
        f"{min(dated)} to {max(dated)}" if len(dated) > 1 else (dated[0] if dated else "not specified")
    )
    hints = template.get("entity_hints") or []
    parts = [
        "You are a senior analyst at CMPDI/CIL preparing an official report section. "
        "Write formal, precise, analytical prose. Numbers are sacred: every figure you "
        "publish must exist verbatim in the FACTS IN SCOPE below and must be cited by its id.",
        f"Template: {template['title']} ({template.get('description', '')})",
        f"Target entities: {', '.join(hints) or 'any relevant'}.",
        f"Section: {section['title']}",
        f"Instructions: {section['prompt']}",
        f"Data coverage: {coverage}.",
    ]
    if facts:
        parts.append(f"FACTS IN SCOPE ({len(facts)}):")
        for fact in facts:
            parts.append(
                f"[id={fact['fact_id']}] entity={fact['entity']} "
                f"value={fact['value']}"
                f"{(' ' + fact['unit']) if fact['unit'] else ''} "
                f"date={fact['date_reference'] or 'n/a'} "
                f"source={fact['document_name']} page={fact['page_number'] or 'n/a'} "
                f'snippet="{fact["raw_snippet"][:160]}"'
            )
    if chunks:
        parts.append(f"SOURCE CHUNKS IN SCOPE ({len(chunks)}):")
        for chunk in chunks[:MAX_CONTEXT_CHUNKS]:
            parts.append(
                f"[chunk={chunk['chunk_id']}] document={chunk['document_name']} "
                f"page={chunk['page_number']}\n{chunk['text'][:500]}"
            )
    parts.append("STYLE RULES:")
    parts.append(
        "- Write flowing prose; do NOT open with a heading, bullet list, or inventory. "
        "Bullets are only allowed when the instruction explicitly asks for a listing."
    )
    parts.append(
        "- The moment you introduce a figure, cite it by referencing its fact id from "
        "FACTS IN SCOPE. Never mention an uncited number."
    )
    parts.append(
        "- Quantify movements only between two dated facts; give the absolute change and "
        "the percentage when the starting value is non-zero. Otherwise use adjectives you "
        "can defend from the cited data."
    )
    parts.append(
        "- If the cited facts are insufficient for what the section asks, write explicitly "
        "that the data does not support such a claim — never invent, extrapolate or guess."
    )
    parts.append(
        "- Target under ~180 words unless the instruction asks for a data listing."
    )
    parts.append(
        "- Assume the reader is CMPDI management; avoid hedging filler words like "
        "'significantly' without evidence."
    )
    parts.append(
        "RULES ON CITATIONS: cite EVERY figure by referencing its fact id from the "
        "FACTS IN SCOPE list. Do not reference ids that were not provided. "
        "If a figure cannot be cited, omit it."
    )
    parts.append(
        'Respond ONLY with strict JSON, no markdown fences: {"body": "<section prose>", '
        '"citations": [{"fact_id": <int>, "document_name": "<name>", '
        '"page_number": <int>}, ...]}'
    )
    return "\n\n".join(parts)


def _citation_from_fact(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        "fact_id": fact["fact_id"],
        "document_name": fact["document_name"],
        "page_number": fact["page_number"],
        "snippet": fact["raw_snippet"],
    }


def _fallback_body(facts: list[dict[str, Any]]) -> str:
    if not facts:
        return "No in-scope facts were available for this section."
    lines = []
    for fact in facts:
        unit = f" {fact['unit']}" if fact["unit"] else ""
        date_text = fact["date_reference"] or "n/a"
        lines.append(
            f"- [{fact['entity']}] {fact['value']}{unit} "
            f"({date_text}, {fact['document_name']}, page {fact['page_number'] or 'n/a'})"
        )
    return (
        "\n".join(lines)
        + "\n\n(Generated without an LLM; every figure above is cited below.)"
    )


def _normalize_citation(citation: SectionCitation, fact_index: dict[int, dict]) -> dict | None:
    fact = fact_index.get(citation.fact_id or -1)
    if fact:
        return {
            "fact_id": fact["fact_id"],
            "document_name": citation.document_name or fact["document_name"],
            "page_number": citation.page_number or fact["page_number"],
            "snippet": fact["raw_snippet"],
        }
    if citation.document_name:
        return {
            "fact_id": None,
            "document_name": citation.document_name,
            "page_number": citation.page_number,
            "snippet": None,
        }
    return None


def _sources_body(citations: list[dict[str, Any]]) -> str:
    lines = []
    for index, citation in enumerate(citations, start=1):
        page = citation.get("page_number") or "n/a"
        fact = (
            f" [fact {citation['fact_id']}]" if citation.get("fact_id") else ""
        )
        lines.append(f"{index}. {citation['document_name']} — page {page}{fact}")
    return "\n".join(lines) if lines else "No sources cited."


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _scope_filter(filters: dict[str, Any]) -> dict[str, Any]:
    """Sanitized copy of the report filter for the cover block."""
    scope: dict[str, Any] = {}
    entities = filters.get("entities") or (
        [filters["entity"]] if filters.get("entity") else None
    )
    if entities:
        scope["entities"] = list(entities)
    if filters.get("date_from"):
        scope["date_from"] = _as_date(filters["date_from"]).isoformat()
    if filters.get("date_to"):
        scope["date_to"] = _as_date(filters["date_to"]).isoformat()
    return scope