"""Shared enumerations for the normalized core schema.

These value sets back the **store** pipeline stage in CLAUDE.md: every
extracted number lands in the same shape regardless of source, so the
source/status enums below must stay stable across modules.
"""

import enum


class SourceType(str, enum.Enum):
    """How an uploaded document reaches the pipeline (ingest/route stage)."""

    scanned_pdf = "scanned_pdf"
    digital_pdf = "digital_pdf"
    image = "image"
    spreadsheet = "spreadsheet"


class DocumentStatus(str, enum.Enum):
    """Lifecycle of a document through ingest -> extract -> store."""

    pending = "pending"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class ConflictStatus(str, enum.Enum):
    """State of a cross-source contradiction in the validate stage."""

    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"


class ReportStatus(str, enum.Enum):
    """Lifecycle of an auto-generated report through human review."""

    draft = "draft"
    reviewed = "reviewed"
    final = "final"