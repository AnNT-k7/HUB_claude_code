"""Add durable assessment runs and realtime event replay.

Revision ID: 20260718_0002
Revises: 20260718_0001
Create Date: 2026-07-18
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260718_0002"
down_revision: Union[str, None] = "20260718_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assessment_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=False),
        sa.Column("checkpoint_stage", sa.String(length=64), nullable=False),
        sa.Column(
            "stop_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("started_by", sa.String(length=255), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'STOP_REQUESTED', 'PAUSED', 'COMPLETED', 'FAILED')",
            name="valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_assessment_runs_case_id_cases", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assessment_runs"),
    )
    op.create_index(
        "ix_assessment_runs_case_id_created_at",
        "assessment_runs",
        ["case_id", "created_at"],
    )

    op.create_table(
        "assessment_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_assessment_events_case_id_cases", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["assessment_runs.id"], name="fk_assessment_events_run_id_assessment_runs", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assessment_events"),
    )
    op.create_index(
        "ix_assessment_events_case_id_id", "assessment_events", ["case_id", "id"]
    )
    op.create_index(
        "ix_assessment_events_run_id_id", "assessment_events", ["run_id", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_assessment_events_run_id_id", table_name="assessment_events")
    op.drop_index("ix_assessment_events_case_id_id", table_name="assessment_events")
    op.drop_table("assessment_events")
    op.drop_index("ix_assessment_runs_case_id_created_at", table_name="assessment_runs")
    op.drop_table("assessment_runs")
