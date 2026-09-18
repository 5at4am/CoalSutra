"""Ingestion pipeline: route → extract → store raw pages (see CLAUDE.md)."""

from app.services.ingestion.orchestrator import ingest_document
from app.services.ingestion.router import classify_document

__all__ = ["classify_document", "ingest_document"]