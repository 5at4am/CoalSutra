"""add human-review columns: conflict resolution verdict + report review note

Revision ID: 0005_add_review_columns
Revises: 0004_document_chunks
Create Date: 2026-09-18 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_add_review_columns"
down_revision: Union[str, None] = "0004_document_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conflict_flags",
        sa.Column(
            "resolution",
            sa.String(32),
            nullable=True,
            comment="Reviewer verdict: fact_a | fact_b | both | neither",
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "review_note",
            sa.String(512),
            nullable=True,
            comment="Reviewer comment when a draft is sent back",
        ),
    )


def downgrade() -> None:
    op.drop_column("reports", "review_note")
    op.drop_column("conflict_flags", "resolution")