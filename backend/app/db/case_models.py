"""Portable (SQLite-default, Postgres-compatible) persistence for the
multi-case Income Verification runtime.

Deliberately separate from ``app/db/models.py``: those models use
Postgres-only types (``pgvector.Vector``, ``JSONB``, native ``UUID``) for the
target production deployment described in ``docs/ARCHITECTURE.md``. This
module backs the case-management API added for the hackathon MVP and must
run with zero external services, so it sticks to generic SQLAlchemy types
that both SQLite and Postgres understand — swapping ``CASE_DATABASE_URL`` to
a Postgres DSN is enough to move this same schema there later.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class CaseBase(DeclarativeBase):
    pass


class CaseRow(CaseBase):
    """One row per income-verification case. ``context_payload`` is the full
    serialized ``CaseContext`` (source of truth for the pipeline); the other
    columns are denormalized read models so ``GET /cases`` can list cases
    without deserializing every payload."""

    __tablename__ = "iv_cases"

    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    application_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_code: Mapped[str | None] = mapped_column(String, nullable=True)
    employer: Mapped[str | None] = mapped_column(String, nullable=True)
    requested_amount: Mapped[str | None] = mapped_column(String, nullable=True)
    loan_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workflow_state: Mapped[str] = mapped_column(String, nullable=False)
    verification_status: Mapped[str | None] = mapped_column(String, nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DocumentRow(CaseBase):
    """Queryable metadata for every uploaded document, independent of the
    (also-persisted) structured facts extracted from it."""

    __tablename__ = "iv_documents"

    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String, ForeignKey("iv_cases.case_id"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    document_type: Mapped[str | None] = mapped_column(String, nullable=True)
    classification_method: Mapped[str | None] = mapped_column(String, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    parse_status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class AuditLogRow(CaseBase):
    """Queryable mirror of ``CaseContext.audit_events``. Rewritten from the
    checkpoint on every save (demo-scale data volume makes this simpler and
    just as correct as incremental appends)."""

    __tablename__ = "iv_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        String, ForeignKey("iv_cases.case_id"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
