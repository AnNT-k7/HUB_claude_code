"""Create the Digital Expert Agents persistence model.

Revision ID: 20260718_0001
Revises: None
Create Date: 2026-07-18
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260718_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("requested_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("workflow_id", sa.String(length=100), nullable=False),
        sa.Column("workflow_version", sa.String(length=32), nullable=False),
        sa.Column(
            "input_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "requested_amount > 0",
            name="ck_cases_requested_amount_positive",
        ),
        sa.CheckConstraint(
            "status IN ('INGESTED', 'TIER1_PLANNING', 'AWAITING_DOCS', "
            "'TIER2_DEBATING', 'TIER3_PENDING_REVIEW', 'REVISION_REQUESTED', "
            "'REJECTED', 'APPROVED', 'COMPLETED')",
            name="ck_cases_valid_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cases"),
    )
    op.create_index(
        "ix_cases_status_created_at", "cases", ["status", "created_at"]
    )

    op.create_table(
        "agent_knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "agent_key IN ('customer_relationship', 'credit', "
            "'risk_management', 'legal_compliance', 'collateral_appraisal')",
            name="ck_agent_knowledge_bases_authorized_agent_key",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_knowledge_bases"),
        sa.UniqueConstraint(
            "agent_key", name="uq_agent_knowledge_bases_agent_key"
        ),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "byte_size >= 0", name="ck_documents_byte_size_non_negative"
        ),
        sa.CheckConstraint(
            "status IN ('UPLOADED', 'PARSED', 'REJECTED')",
            name="ck_documents_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name="fk_documents_case_id_cases",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint("object_key", name="uq_documents_object_key"),
    )
    op.create_index(
        "ix_documents_case_id_created_at",
        "documents",
        ["case_id", "created_at"],
    )

    op.create_table(
        "shared_boards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.String(length=100), nullable=False),
        sa.Column("workflow_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "task_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "specialist_outputs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "final_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "missing_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "consensus_reached",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "current_debate_round",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "review_cycle",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "max_debate_rounds",
            sa.Integer(),
            server_default=sa.text("3"),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "current_debate_round >= 0",
            name="ck_shared_boards_round_non_negative",
        ),
        sa.CheckConstraint(
            "current_debate_round <= max_debate_rounds",
            name="ck_shared_boards_round_within_maximum",
        ),
        sa.CheckConstraint(
            "max_debate_rounds > 0",
            name="ck_shared_boards_max_rounds_positive",
        ),
        sa.CheckConstraint(
            "version >= 0", name="ck_shared_boards_version_non_negative"
        ),
        sa.CheckConstraint(
            "review_cycle > 0", name="ck_shared_boards_review_cycle_positive"
        ),
        sa.CheckConstraint(
            "status IN ('INITIALIZED', 'SPECIALISTS_RUNNING', "
            "'DEBATE_IN_PROGRESS', 'CONSENSUS_REACHED', "
            "'MAX_ROUNDS_REACHED')",
            name="ck_shared_boards_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name="fk_shared_boards_case_id_cases",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shared_boards"),
        sa.UniqueConstraint("case_id", name="uq_shared_boards_case_id"),
    )

    op.create_table(
        "debate_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("review_cycle", sa.Integer(), nullable=False),
        sa.Column("critic_agent", sa.String(length=100), nullable=False),
        sa.Column("target_agent", sa.String(length=100), nullable=False),
        sa.Column("issue_code", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("related_field", sa.String(length=255), nullable=True),
        sa.Column("error_identified", sa.Text(), nullable=False),
        sa.Column("required_action", sa.Text(), nullable=False),
        sa.Column("specialist_response", sa.Text(), nullable=True),
        sa.Column("resolution_applied", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "round_number > 0", name="ck_debate_logs_round_positive"
        ),
        sa.CheckConstraint(
            "review_cycle > 0", name="ck_debate_logs_review_cycle_positive"
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'RESOLVED', 'ACCEPTED_FOR_MANUAL_REVIEW')",
            name="ck_debate_logs_valid_status",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_debate_logs_valid_severity",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name="fk_debate_logs_case_id_cases",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_debate_logs"),
        sa.UniqueConstraint(
            "case_id",
            "review_cycle",
            "round_number",
            "issue_code",
            "target_agent",
            name="uq_debate_logs_case_cycle_round_issue_target",
        ),
    )
    op.create_index(
        "ix_debate_logs_case_id_cycle_round",
        "debate_logs",
        ["case_id", "review_cycle", "round_number"],
    )

    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verified_by", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVED', 'REJECTED', 'REVISION_REQUESTED')",
            name="ck_approvals_valid_decision",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name="fk_approvals_case_id_cases",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approvals"),
        sa.UniqueConstraint("case_id", name="uq_approvals_case_id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column(
            "payload_trace",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('STARTED', 'SUCCEEDED', 'FAILED', 'BLOCKED')",
            name="ck_audit_logs_valid_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name="fk_audit_logs_case_id_cases",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index(
        "ix_audit_logs_case_id_created_at",
        "audit_logs",
        ["case_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"]
    )

    op.create_table(
        "operation_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "request_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "response_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "artifact_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name="ck_operation_executions_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name="fk_operation_executions_case_id_cases",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_operation_executions"),
        sa.UniqueConstraint(
            "case_id", name="uq_operation_executions_case_id"
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_operation_executions_idempotency_key",
        ),
    )
    op.create_index(
        "ix_operation_executions_status_created_at",
        "operation_executions",
        ["status", "created_at"],
    )

    op.create_table(
        "policy_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("source_object_key", sa.String(length=1024), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["agent_knowledge_bases.id"],
            name=(
                "fk_policy_documents_knowledge_base_id_agent_knowledge_bases"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_documents"),
        sa.UniqueConstraint(
            "knowledge_base_id",
            "title",
            "version",
            name="uq_policy_documents_kb_title_version",
        ),
        sa.UniqueConstraint(
            "id",
            "knowledge_base_id",
            name="uq_policy_documents_id_knowledge_base_id",
        ),
    )
    op.create_index(
        "ix_policy_documents_knowledge_base_id",
        "policy_documents",
        ["knowledge_base_id"],
    )

    op.create_table(
        "policy_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "policy_document_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_chunk", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(dim=1024), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name="ck_policy_embeddings_chunk_index_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["agent_knowledge_bases.id"],
            name=(
                "fk_policy_embeddings_knowledge_base_id_agent_knowledge_bases"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["policy_document_id", "knowledge_base_id"],
            ["policy_documents.id", "policy_documents.knowledge_base_id"],
            name="fk_policy_embeddings_document_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_embeddings"),
        sa.UniqueConstraint(
            "policy_document_id",
            "content_hash",
            name="uq_policy_embeddings_document_content_hash",
        ),
    )
    op.create_index(
        "ix_policy_embeddings_knowledge_base_id",
        "policy_embeddings",
        ["knowledge_base_id"],
    )
    op.create_index(
        "ix_policy_embeddings_policy_document_id",
        "policy_embeddings",
        ["policy_document_id"],
    )
    op.execute(
        "CREATE INDEX ix_policy_embeddings_embedding_hnsw "
        "ON policy_embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    op.execute(
        """
        CREATE FUNCTION reject_audit_log_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only; % is forbidden', TG_OP
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_append_only
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation()")
    op.drop_table("policy_embeddings")
    op.drop_table("policy_documents")
    op.drop_table("operation_executions")
    op.drop_table("audit_logs")
    op.drop_table("approvals")
    op.drop_table("debate_logs")
    op.drop_table("shared_boards")
    op.drop_table("documents")
    op.drop_table("agent_knowledge_bases")
    op.drop_table("cases")
