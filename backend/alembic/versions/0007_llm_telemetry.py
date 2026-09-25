"""add llm_usage and eval_runs tables for the Evaluate dashboard

Revision ID: 0007_llm_telemetry
Revises: 0006_add_ingestion_jobs
Create Date: 2026-09-25 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_llm_telemetry"
down_revision: Union[str, None] = "0006_add_ingestion_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "endpoint",
            sa.String(32),
            nullable=False,
            server_default="generic",
            index=True,
        ),
        sa.Column("prompt_label", sa.String(240), nullable=True),
        sa.Column("model", sa.String(64), nullable=False, server_default=""),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float, nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "mode",
            sa.String(16),
            nullable=False,
            server_default="retrieval",
        ),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column(
            "questions_evaluated",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("passed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("retrieval_recall", sa.Float, nullable=False, server_default="0"),
        sa.Column("answer_accuracy", sa.Float, nullable=True),
        sa.Column("refusal_passed", sa.Boolean, nullable=True),
        sa.Column("per_case", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("summary", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("duration_ms", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("eval_runs")
    op.drop_table("llm_usage")