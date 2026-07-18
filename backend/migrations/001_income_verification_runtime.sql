-- Target MVP persistence for the income-verification workflow.
-- Apply after enabling the pgvector extension used by policy_embeddings.

CREATE TABLE IF NOT EXISTS verification_checkpoints (
    case_id VARCHAR PRIMARY KEY,
    application_id VARCHAR NOT NULL,
    state_version INTEGER NOT NULL DEFAULT 0,
    workflow_state VARCHAR NOT NULL,
    context_payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_verification_checkpoints_application_id
    ON verification_checkpoints (application_id);

CREATE TABLE IF NOT EXISTS verification_action_executions (
    id UUID PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    action_id VARCHAR NOT NULL,
    idempotency_key VARCHAR NOT NULL UNIQUE,
    status VARCHAR NOT NULL,
    result_reference VARCHAR,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_verification_action_executions_case_id
    ON verification_action_executions (case_id);

CREATE TABLE IF NOT EXISTS verification_audit_events (
    id UUID PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    actor_type VARCHAR NOT NULL,
    actor_id VARCHAR,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_verification_audit_events_case_id
    ON verification_audit_events (case_id, created_at);
