"""Normalize (LLM) and validate (cross-source conflict detection).

The **normalize** and **validate** stages of the CLAUDE.md pipeline:
`normalizer` turns extracted page text into `ExtractedFact` rows via a strict
LLM extraction (with a deterministic rule-based fallback when no API key is
set), and `validator` flags cross-document value conflicts rather than
silently overwriting a stored figure.
"""