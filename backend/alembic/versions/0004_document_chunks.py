"""add document_chunks table (page-text chunks with pgvector embeddings)

Revision ID: 0004_document_chunks
Revises: 0003_document_pages
Create Date: 2026-09-18 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy as pgv
import sqlalchemy as sa

revision: str = "0004_document_chunks"
down_revision: Union[str, None] = "0003_document_pages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match settings.EMBEDDING_DIM (embeddings are stored in this column).
EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "embedding",
            pgv.Vector(dim=EMBEDDING_DIM),
            nullable=True,
            comment="Embedded chunk vector, sized EMBEDDING_DIM",
        ),
        sa.Comment(
            "Embeddable chunks of page text for the query/retrieval stage"
        ),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")