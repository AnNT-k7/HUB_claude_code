"""Multi-case orchestration layer backing the case-management REST API.

This is the generalized replacement for the old single-fixed-case
``IncomeVerificationRuntime`` (``app/services/runtime.py``, still kept
as-is for backward compatibility with the original demo endpoints). Every
case here is created dynamically, its documents are uploaded and persisted
to disk + SQLite, and the same LangGraph orchestrator/agents run against
whatever was actually uploaded — there is no hardcoded case id anywhere in
this module.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, select

from app.agents.income_verification import (
    CaseContext,
    IncomeAnalysisAgent,
    IncomeVerificationOrchestrator,
    PolicyAgent,
    WorkflowConfig,
    WorkflowDependencies,
)
from app.agents.income_verification.general_document_agent import (
    DocumentIndex,
    GeneralDocumentAgent,
    IndexedDocument,
)
from app.agents.income_verification.human_review import (
    HumanReviewCommand,
    apply_human_review,
)
from app.agents.income_verification.orchestrator import CheckpointStore, ConcurrentStateError
from app.agents.income_verification.state import AuditEvent, WorkflowState
from app.config import get_settings
from app.db.case_models import AuditLogRow, CaseRow, DocumentRow
from app.db.case_session import CaseSessionLocal, init_case_db
from app.services.action_executor import ActionExecutor
from app.services.case_document_store import (
    DocumentStorageError,
    read_document,
    save_upload,
)
from app.services.llm_provider import LLMProvider, build_llm_provider
from app.agents.income_verification.policy_agent import NamespacePolicyRetriever
from app.services.runtime import EmbeddedDemoPolicyRetriever


class CaseNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class CaseSummary:
    case_id: str
    application_id: str
    customer_name: str | None
    employer: str | None
    requested_amount: str | None
    loan_term_months: int | None
    workflow_state: str
    verification_status: str | None
    document_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    document_id: str
    file_name: str
    content_type: str
    document_type: str | None
    classification_method: str | None
    checksum: str
    size_bytes: int
    parse_status: str
    uploaded_at: datetime


class SqlCaseCheckpointStore:
    """CheckpointStore backed by iv_cases; also mirrors audit events into
    the queryable iv_audit_logs table on every save."""

    async def load(self, case_id: str) -> CaseContext | None:
        return await asyncio.to_thread(self._load_sync, case_id)

    async def save(self, context: CaseContext, *, expected_version: int) -> None:
        await asyncio.to_thread(self._save_sync, context, expected_version)

    def _load_sync(self, case_id: str) -> CaseContext | None:
        with CaseSessionLocal() as session:
            row = session.get(CaseRow, case_id)
            return CaseContext.model_validate(row.context_payload) if row else None

    def _save_sync(self, context: CaseContext, expected_version: int) -> None:
        with CaseSessionLocal() as session:
            row = session.get(CaseRow, context.case_id)
            current_version = row.state_version if row is not None else 0
            if current_version != expected_version:
                raise ConcurrentStateError(f"Case {context.case_id} checkpoint version changed")
            payload = context.model_dump(mode="json")
            extracted = context.extracted_fields
            if row is None:
                row = CaseRow(
                    case_id=context.case_id,
                    application_id=context.application_id,
                    workflow_state=context.workflow_state.value,
                    state_version=context.state_version,
                    context_payload=payload,
                )
                session.add(row)
            row.workflow_state = context.workflow_state.value
            row.state_version = context.state_version
            row.context_payload = payload
            if extracted is not None:
                row.customer_name = extracted.customer_name or row.customer_name
                row.employer = extracted.employer or row.employer
            if context.recommendation is not None:
                row.verification_status = context.recommendation.status.value
            session.execute(delete(AuditLogRow).where(AuditLogRow.case_id == context.case_id))
            for event in context.audit_events:
                session.add(
                    AuditLogRow(
                        case_id=context.case_id,
                        event_id=event.event_id,
                        event_type=event.event_type,
                        actor_type=event.actor_type,
                        actor_id=event.actor_id,
                        details=event.details,
                        created_at=event.created_at,
                    )
                )
            session.commit()


class SqlDocumentIndex:
    """DocumentIndex reading uploaded-file metadata from SQLite and bytes
    from local disk — the port GeneralDocumentAgent uses to see a case's
    documents regardless of which case_id the orchestrator is running."""

    def list_documents(self, case_id: str) -> list[IndexedDocument]:
        with CaseSessionLocal() as session:
            rows = session.execute(
                select(DocumentRow).where(DocumentRow.case_id == case_id)
            ).scalars().all()
        items: list[IndexedDocument] = []
        for row in rows:
            try:
                raw_bytes = read_document(case_id=case_id, storage_path=row.storage_path)
            except DocumentStorageError:
                continue
            items.append(
                IndexedDocument(
                    document_id=row.document_id,
                    file_name=row.file_name,
                    content_type=row.content_type,
                    raw_bytes=raw_bytes,
                )
            )
        return items


def _select_policy_retriever(settings):
    """Real embedding-based retrieval when an embedding key is configured;
    an explicit, audit-logged degraded fallback otherwise. Mirrors the
    provider-selection pattern already used for the chat LLM."""

    key_present = (
        bool(settings.fpt_api_key.strip())
        if settings.embedding_provider == "fpt"
        else bool(settings.glm_api_key.strip()) if settings.embedding_provider == "glm" else True
    )
    if key_present:
        return NamespacePolicyRetriever(), "EMBEDDING_RAG"
    return EmbeddedDemoPolicyRetriever(), "DEGRADED_KEYWORD_MATCH"


class CaseService:
    """Owns case CRUD, document upload, and pipeline execution for the
    generalized multi-case runtime."""

    def __init__(
        self,
        *,
        llm: LLMProvider | None = None,
        policy_retriever: object | None = None,
        checkpoints: CheckpointStore | None = None,
    ) -> None:
        """``llm``/``policy_retriever``/``checkpoints`` overrides exist so
        tests (e.g. tests/test_synthetic_cases.py) can force deterministic,
        network-free behavior without changing the real-provider default
        ``get_case_service()`` uses."""

        init_case_db()
        settings = get_settings()
        self.llm = llm or build_llm_provider(settings)
        self.document_index = SqlDocumentIndex()
        self.document_agent = GeneralDocumentAgent(self.document_index, llm=self.llm)
        if policy_retriever is not None:
            retriever, self.rag_mode = policy_retriever, "INJECTED"
        else:
            retriever, self.rag_mode = _select_policy_retriever(settings)
        self.checkpoints: CheckpointStore = checkpoints or SqlCaseCheckpointStore()
        self.orchestrator = IncomeVerificationOrchestrator(
            WorkflowDependencies(
                fetch_documents=self.document_agent.fetch_documents,
                extract_documents=self.document_agent,
                analyze_income=IncomeAnalysisAgent(),
                retrieve_policy=PolicyAgent(retriever, llm=self.llm),
            ),
            checkpoint_store=self.checkpoints,
            # LLM-assisted extraction/classification calls (several per
            # case: one per document + one consolidated field-extraction
            # call) take real wall-clock time — the 30s default was sized
            # for the purely deterministic fixture pipeline.
            config=WorkflowConfig(component_timeout_seconds=120.0),
        )
        self.action_executor = ActionExecutor()
        self._lock = asyncio.Lock()

    # -- case CRUD ---------------------------------------------------

    async def create_case(
        self,
        *,
        customer_name: str | None,
        customer_code: str | None,
        employer: str | None,
        requested_amount: Decimal | None,
        loan_term_months: int | None,
    ) -> CaseContext:
        case_id = f"IV-{uuid.uuid4().hex[:10].upper()}"
        application_id = f"APP-{uuid.uuid4().hex[:8].upper()}"
        context = CaseContext(case_id=case_id, application_id=application_id)
        context.add_event(
            "CASE_CREATED",
            actor_type="SYSTEM",
            details={
                "customer_name": customer_name,
                "employer": employer,
                "rag_mode": self.rag_mode,
                "llm_mode": self.llm.mode_label,
            },
        )

        def _insert() -> None:
            with CaseSessionLocal() as session:
                session.add(
                    CaseRow(
                        case_id=case_id,
                        application_id=application_id,
                        customer_name=customer_name,
                        customer_code=customer_code,
                        employer=employer,
                        requested_amount=str(requested_amount) if requested_amount is not None else None,
                        loan_term_months=loan_term_months,
                        workflow_state=context.workflow_state.value,
                        state_version=context.state_version,
                        context_payload=context.model_dump(mode="json"),
                    )
                )
                session.commit()

        await asyncio.to_thread(_insert)
        return context

    async def list_cases(self) -> list[CaseSummary]:
        def _query() -> list[CaseSummary]:
            with CaseSessionLocal() as session:
                rows = session.execute(
                    select(CaseRow).order_by(CaseRow.created_at.desc())
                ).scalars().all()
                summaries = []
                for row in rows:
                    doc_count = session.execute(
                        select(DocumentRow).where(DocumentRow.case_id == row.case_id)
                    ).scalars().all()
                    summaries.append(
                        CaseSummary(
                            case_id=row.case_id,
                            application_id=row.application_id,
                            customer_name=row.customer_name,
                            employer=row.employer,
                            requested_amount=row.requested_amount,
                            loan_term_months=row.loan_term_months,
                            workflow_state=row.workflow_state,
                            verification_status=row.verification_status,
                            document_count=len(doc_count),
                            created_at=row.created_at,
                            updated_at=row.updated_at,
                        )
                    )
                return summaries

        return await asyncio.to_thread(_query)

    async def get_case(self, case_id: str) -> CaseContext:
        context = await self.checkpoints.load(case_id)
        if context is None:
            raise CaseNotFoundError(case_id)
        return context

    # -- documents -----------------------------------------------------

    async def add_document(
        self,
        case_id: str,
        *,
        file_name: str,
        content_type: str,
        raw_bytes: bytes,
        document_type_hint: str | None = None,
    ) -> DocumentSummary:
        await self.get_case(case_id)  # raises CaseNotFoundError if missing
        document_id = f"doc-{uuid.uuid4().hex[:12]}"
        path, checksum = save_upload(
            case_id=case_id, document_id=document_id, file_name=file_name, content=raw_bytes
        )

        def _insert() -> DocumentSummary:
            with CaseSessionLocal() as session:
                row = DocumentRow(
                    document_id=document_id,
                    case_id=case_id,
                    file_name=file_name,
                    content_type=content_type,
                    document_type=document_type_hint,
                    classification_method="USER_HINT" if document_type_hint else None,
                    checksum=checksum,
                    size_bytes=len(raw_bytes),
                    storage_path=str(path),
                    parse_status="PENDING",
                )
                session.add(row)
                session.commit()
                return DocumentSummary(
                    document_id=row.document_id,
                    file_name=row.file_name,
                    content_type=row.content_type,
                    document_type=row.document_type,
                    classification_method=row.classification_method,
                    checksum=row.checksum,
                    size_bytes=row.size_bytes,
                    parse_status=row.parse_status,
                    uploaded_at=row.uploaded_at,
                )

        summary = await asyncio.to_thread(_insert)
        context = await self.get_case(case_id)
        context.add_event(
            "DOCUMENT_UPLOADED",
            actor_type="UNDERWRITER",
            details={"document_id": document_id, "file_name": file_name},
        )
        await self.checkpoints.save(context, expected_version=context.state_version - 1)
        return summary

    async def get_document_bytes(self, case_id: str, document_id: str) -> tuple[bytes, str, str]:
        """Returns (raw_bytes, file_name, content_type) for the evidence
        viewer's "download / open source file" affordance."""

        def _query() -> DocumentRow | None:
            with CaseSessionLocal() as session:
                row = session.execute(
                    select(DocumentRow).where(
                        DocumentRow.case_id == case_id, DocumentRow.document_id == document_id
                    )
                ).scalar_one_or_none()
                return row

        row = await asyncio.to_thread(_query)
        if row is None:
            raise DocumentStorageError("DOCUMENT_NOT_FOUND_FOR_CASE")
        raw_bytes = read_document(case_id=case_id, storage_path=row.storage_path)
        return raw_bytes, row.file_name, row.content_type

    async def list_documents(self, case_id: str) -> list[DocumentSummary]:
        def _query() -> list[DocumentSummary]:
            with CaseSessionLocal() as session:
                rows = session.execute(
                    select(DocumentRow).where(DocumentRow.case_id == case_id)
                ).scalars().all()
                return [
                    DocumentSummary(
                        document_id=row.document_id,
                        file_name=row.file_name,
                        content_type=row.content_type,
                        document_type=row.document_type,
                        classification_method=row.classification_method,
                        checksum=row.checksum,
                        size_bytes=row.size_bytes,
                        parse_status=row.parse_status,
                        uploaded_at=row.uploaded_at,
                    )
                    for row in rows
                ]

        return await asyncio.to_thread(_query)

    # -- pipeline --------------------------------------------------------

    async def run_pipeline(self, case_id: str) -> CaseContext:
        async with self._lock:
            context = await self.get_case(case_id)
            if context.workflow_state is WorkflowState.OPEN_CASE:
                context.transition_to(WorkflowState.FETCHING_DOCUMENTS)
                await self.checkpoints.save(context, expected_version=context.state_version - 1)
            return await self.orchestrator.run(context)

    async def review(self, case_id: str, command: HumanReviewCommand, *, reviewer_id: str) -> CaseContext:
        async with self._lock:
            previous = await self.get_case(case_id)
            reviewed = apply_human_review(previous, command, reviewer_id=reviewer_id)
            await self.checkpoints.save(reviewed, expected_version=previous.state_version)
            if command.outcome.value == "EDIT_AND_RERUN":
                return await self.orchestrator.run(reviewed)
            if command.outcome.value != "ACCEPT_ACTIONS":
                return reviewed
            executed = await self.action_executor.execute(reviewed)
            await self.checkpoints.save(executed, expected_version=reviewed.state_version)
            return executed

    async def retry_actions(self, case_id: str) -> CaseContext:
        async with self._lock:
            previous = await self.get_case(case_id)
            executed = await self.action_executor.execute(previous)
            await self.checkpoints.save(executed, expected_version=previous.state_version)
            return executed


_case_service: CaseService | None = None


def get_case_service() -> CaseService:
    global _case_service
    if _case_service is None:
        _case_service = CaseService()
    return _case_service
