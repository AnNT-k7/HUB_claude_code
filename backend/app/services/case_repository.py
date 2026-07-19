"""SQLite/PostgreSQL repository for multi-case income verification."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.income_verification.state import CaseContext
from app.config import Settings, get_settings
from app.db.models import (
    AgentResultRecord,
    AgentRunRecord,
    EvidenceRecord,
    FinalReportRecord,
    IncomeAuditLog,
    IncomeCase,
    IncomeDocument,
)
from app.db.session import SessionLocal, initialize_mvp_database


SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md", ".csv"}
SUPPORTED_DOCUMENT_TYPES = {
    "LOAN_APPLICATION",
    "EMPLOYMENT_CONTRACT",
    "PAYSLIP_BUNDLE",
    "BANK_STATEMENT",
}


class CaseRepositoryError(ValueError):
    pass


class CaseNotFound(CaseRepositoryError):
    pass


class DocumentNotFound(CaseRepositoryError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_filename(name: str) -> str:
    leaf = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", leaf).strip("._")
    return cleaned or "document"


class CaseRepository:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] = SessionLocal,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.storage_root = Path(self.settings.document_storage_root).resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        initialize_mvp_database(self.session_factory.kw.get("bind"))

    def create_case(
        self,
        *,
        customer_name: str,
        customer_code: str | None = None,
        company: str,
        requested_amount: Decimal,
        currency: str = "VND",
        application_id: str | None = None,
        case_id: str | None = None,
    ) -> IncomeCase:
        now = _utc_now()
        row = IncomeCase(
            id=case_id or f"IV-{uuid4().hex[:12].upper()}",
            application_id=application_id or f"APP-{uuid4().hex[:12].upper()}",
            customer_name=customer_name.strip(),
            customer_code=customer_code.strip() if customer_code else f"CUS-{uuid4().hex[:10].upper()}",
            company=company.strip(),
            requested_amount=requested_amount,
            currency=currency.upper(),
            status="DRAFT",
            pipeline_status="OPEN_CASE",
            state_version=0,
            created_at=now,
            updated_at=now,
        )
        with self.session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            self._append_audit(
                session,
                case_id=row.id,
                event_type="CASE_CREATED",
                details={"application_id": row.application_id},
            )
            session.commit()
            session.expunge(row)
        return row

    def list_cases(self) -> list[IncomeCase]:
        with self.session_factory() as session:
            rows = list(session.scalars(select(IncomeCase).order_by(IncomeCase.created_at.desc())))
            for row in rows:
                session.expunge(row)
            return rows

    def get_case(self, case_id: str) -> IncomeCase:
        with self.session_factory() as session:
            row = session.get(IncomeCase, case_id)
            if row is None:
                raise CaseNotFound(case_id)
            session.expunge(row)
            return row

    def get_by_application(self, application_id: str) -> IncomeCase | None:
        with self.session_factory() as session:
            row = session.scalar(select(IncomeCase).where(IncomeCase.application_id == application_id))
            if row is not None:
                session.expunge(row)
            return row

    def add_document(
        self,
        *,
        case_id: str,
        file_name: str,
        content_type: str,
        document_type: str,
        content: bytes,
    ) -> IncomeDocument:
        self.get_case(case_id)
        normalized_document_type = document_type.strip().upper()
        if normalized_document_type not in SUPPORTED_DOCUMENT_TYPES:
            raise CaseRepositoryError("UNSUPPORTED_DOCUMENT_TYPE")
        suffix = Path(file_name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise CaseRepositoryError("UNSUPPORTED_DOCUMENT_FORMAT")
        if not content:
            raise CaseRepositoryError("EMPTY_DOCUMENT")
        if len(content) > self.settings.max_document_size_bytes:
            raise CaseRepositoryError("DOCUMENT_TOO_LARGE")
        checksum = "sha256:" + hashlib.sha256(content).hexdigest()
        document_id = f"DOC-{uuid4().hex[:12].upper()}"
        case_root = self.storage_root / case_id
        case_root.mkdir(parents=True, exist_ok=True)
        storage_path = case_root / f"{document_id}_{_safe_filename(file_name)}"
        storage_path.write_bytes(content)
        row = IncomeDocument(
            id=document_id,
            case_id=case_id,
            file_name=Path(file_name).name,
            content_type=content_type or "application/octet-stream",
            document_type=normalized_document_type,
            storage_path=str(storage_path),
            checksum=checksum,
            size_bytes=len(content),
            processing_status="UPLOADED",
            uploaded_at=_utc_now(),
        )
        with self.session_factory() as session:
            duplicate = session.scalar(
                select(IncomeDocument).where(
                    IncomeDocument.case_id == case_id,
                    IncomeDocument.checksum == checksum,
                )
            )
            if duplicate is not None:
                storage_path.unlink(missing_ok=True)
                raise CaseRepositoryError("DUPLICATE_DOCUMENT")
            session.add(row)
            self._append_audit(
                session,
                case_id=case_id,
                event_type="DOCUMENT_UPLOADED",
                details={"document_id": document_id, "document_type": row.document_type},
            )
            session.commit()
            session.expunge(row)
        return row

    def list_documents(self, case_id: str) -> list[IncomeDocument]:
        self.get_case(case_id)
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(IncomeDocument)
                    .where(IncomeDocument.case_id == case_id)
                    .order_by(IncomeDocument.uploaded_at)
                )
            )
            for row in rows:
                session.expunge(row)
            return rows

    def get_document(self, case_id: str, document_id: str) -> IncomeDocument:
        with self.session_factory() as session:
            row = session.get(IncomeDocument, document_id)
            if row is None or row.case_id != case_id:
                raise DocumentNotFound(document_id)
            session.expunge(row)
            return row

    def update_document_processing(
        self,
        document_id: str,
        *,
        status: str,
        page_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            row = session.get(IncomeDocument, document_id)
            if row is None:
                raise DocumentNotFound(document_id)
            row.processing_status = status
            row.page_count = page_count
            row.error_message = error_message
            session.commit()

    def load_context(self, case_id: str) -> CaseContext | None:
        row = self.get_case(case_id)
        return CaseContext.model_validate(row.context_payload) if row.context_payload else None

    def save_context(self, context: CaseContext) -> None:
        with self.session_factory() as session:
            row = session.get(IncomeCase, context.case_id)
            if row is None:
                raise CaseNotFound(context.case_id)
            row.context_payload = context.model_dump(mode="json")
            row.pipeline_status = context.workflow_state.value
            row.status = (
                context.recommendation.status.value
                if context.recommendation is not None
                else context.workflow_state.value
            )
            row.state_version = context.state_version
            row.updated_at = _utc_now()
            existing_events = {
                value
                for value in session.scalars(
                    select(IncomeAuditLog.id).where(IncomeAuditLog.case_id == context.case_id)
                )
            }
            for event in context.audit_events:
                if event.event_id in existing_events:
                    continue
                session.add(
                    IncomeAuditLog(
                        id=event.event_id,
                        case_id=context.case_id,
                        actor_type=event.actor_type,
                        actor_id=event.actor_id,
                        event_type=event.event_type,
                        details=event.model_dump(mode="json"),
                        created_at=event.created_at,
                    )
                )
            existing_evidence = {
                value
                for value in session.scalars(
                    select(EvidenceRecord.id).where(EvidenceRecord.case_id == context.case_id)
                )
            }
            for evidence in context.evidence:
                if evidence.evidence_id in existing_evidence:
                    continue
                session.add(
                    EvidenceRecord(
                        id=evidence.evidence_id,
                        case_id=context.case_id,
                        document_id=evidence.document_id,
                        field_name=evidence.field_name,
                        page_number=evidence.page_number,
                        text_quote=evidence.quote,
                        location=evidence.location,
                        extraction_method=evidence.extraction_method,
                        confidence=evidence.confidence,
                        source_checksum=evidence.source_checksum or "unknown",
                    )
                )
            if context.recommendation is not None:
                report = session.scalar(
                    select(FinalReportRecord).where(FinalReportRecord.case_id == context.case_id)
                )
                payload = context.recommendation.model_dump(mode="json")
                if report is None:
                    session.add(
                        FinalReportRecord(
                            id=f"REPORT-{uuid4().hex[:12].upper()}",
                            case_id=context.case_id,
                            status=context.recommendation.status.value,
                            report_payload=payload,
                            created_at=_utc_now(),
                        )
                    )
                else:
                    report.status = context.recommendation.status.value
                    report.report_payload = payload
            session.commit()

    def reset_context(self, case_id: str) -> None:
        with self.session_factory() as session:
            row = session.get(IncomeCase, case_id)
            if row is None:
                raise CaseNotFound(case_id)
            row.context_payload = None
            row.pipeline_status = "OPEN_CASE"
            row.status = "DRAFT"
            row.state_version = 0
            row.updated_at = _utc_now()
            self._append_audit(
                session,
                case_id=case_id,
                event_type="PIPELINE_RESET_FOR_RERUN",
                details={},
            )
            session.commit()

    def record_agent_result(
        self,
        *,
        case_id: str,
        agent_name: str,
        status: str,
        result_payload: dict[str, object],
        llm_provider: str,
        model_name: str | None,
        confidence: float | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        run_id = f"RUN-{uuid4().hex[:16].upper()}"
        with self.session_factory() as session:
            session.add(
                AgentRunRecord(
                    id=run_id,
                    case_id=case_id,
                    agent_name=agent_name,
                    status=status,
                    llm_provider=llm_provider,
                    model_name=model_name,
                    warnings=warnings or [],
                    started_at=_utc_now(),
                    completed_at=_utc_now(),
                )
            )
            session.add(
                AgentResultRecord(
                    id=f"RESULT-{uuid4().hex[:16].upper()}",
                    case_id=case_id,
                    agent_run_id=run_id,
                    result_payload=result_payload,
                    confidence=confidence,
                    created_at=_utc_now(),
                )
            )
            session.commit()

    def list_agent_runs(self, case_id: str) -> list[dict[str, object]]:
        with self.session_factory() as session:
            runs = list(
                session.scalars(
                    select(AgentRunRecord)
                    .where(AgentRunRecord.case_id == case_id)
                    .order_by(AgentRunRecord.started_at)
                )
            )
            return [
                {
                    "id": run.id,
                    "agent_name": run.agent_name,
                    "status": run.status,
                    "llm_provider": run.llm_provider,
                    "model_name": run.model_name,
                    "warnings": run.warnings,
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                }
                for run in runs
            ]

    def list_audit(self, case_id: str) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(IncomeAuditLog)
                    .where(IncomeAuditLog.case_id == case_id)
                    .order_by(IncomeAuditLog.created_at)
                )
            )
            return [
                {
                    "event_id": row.id,
                    "event_type": row.event_type,
                    "actor_type": row.actor_type,
                    "actor_id": row.actor_id,
                    "details": row.details,
                    "created_at": row.created_at,
                }
                for row in rows
            ]

    @staticmethod
    def _append_audit(
        session: Session,
        *,
        case_id: str,
        event_type: str,
        details: dict[str, object],
    ) -> None:
        session.add(
            IncomeAuditLog(
                id=str(uuid4()),
                case_id=case_id,
                actor_type="SYSTEM",
                actor_id=None,
                event_type=event_type,
                details=details,
                created_at=_utc_now(),
            )
        )
