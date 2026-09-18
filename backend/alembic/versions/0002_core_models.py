"""add core normalized schema (documents, facts, conflicts, reports, topics)

Revision ID: 0002_core_models
Revises: 0001_pgvector
Create Date: 2026-09-17 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_core_models"
down_revision: Union[str, None] = "0001_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("upload_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_file_path", sa.String(length=512), nullable=False),
    )

    op.create_table(
        "extracted_facts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity", sa.String(length=255), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("date_reference", sa.Date(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("raw_snippet", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
    )
    op.create_index(
        "ix_extracted_facts_document_id", "extracted_facts", ["document_id"]
    )

    op.create_table(
        "conflict_flags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "fact_a_id",
            sa.Integer(),
            sa.ForeignKey("extracted_facts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fact_b_id",
            sa.Integer(),
            sa.ForeignKey("extracted_facts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolved_by", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_conflict_flags_fact_a_id", "conflict_flags", ["fact_a_id"])
    op.create_index("ix_conflict_flags_fact_b_id", "conflict_flags", ["fact_b_id"])

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("template_type", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("export_path", sa.String(length=512), nullable=True),
    )

    op.create_table(
        "topic_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("corpus_filter", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("topic_runs")
    op.drop_table("reports")
    op.drop_index("ix_conflict_flags_fact_b_id", table_name="conflict_flags")
    op.drop_index("ix_conflict_flags_fact_a_id", table_name="conflict_flags")
    op.drop_table("conflict_flags")
    op.drop_index("ix_extracted_facts_document_id", table_name="extracted_facts")
    op.drop_table("extracted_facts")
    op.drop_table("documents")