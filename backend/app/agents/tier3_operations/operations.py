from __future__ import annotations

import io
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from pydantic import Field
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import (
    Approval,
    ApprovalDecision,
    AuditOutcome,
    Case,
    CaseStatus,
    OperationExecution,
    OperationStatus,
    SharedBoard,
)
from app.mock_apis.mock_endpoints import MockOnboardingRequest
from app.mock_apis.shb_client import HttpMockShbClient, MockShbGateway
from app.schemas.api import (
    OperationArtifactResponse,
    OperationExecutionResponse,
)
from app.schemas.base import ContractModel
from app.schemas.enums import AgentID
from app.services.audit import write_audit_log
from app.services.llm import OpenAICompatibleStructuredLLM, StructuredLLM
from app.services.storage import ObjectStorage


class OperationsBlockedError(RuntimeError):
    pass


class OperationsInProgressError(RuntimeError):
    pass


class DraftAgreementContent(ContractModel):
    title: str = Field(min_length=1, max_length=255)
    purpose: str = Field(min_length=1, max_length=2_000)
    preliminary_terms: list[str] = Field(min_length=1, max_length=30)
    conditions_precedent: list[str] = Field(default_factory=list, max_length=30)
    disclaimer: str = Field(min_length=1, max_length=1_000)


GatewayFactory = Callable[[], MockShbGateway]
LLMFactory = Callable[[], StructuredLLM]


class BankingOperationsAgent:
    """Post-human-approval agent restricted to local Mock SHB APIs."""

    def __init__(
        self,
        db: Session,
        storage: ObjectStorage,
        *,
        settings: Settings | None = None,
        gateway_factory: GatewayFactory | None = None,
        llm_factory: LLMFactory | None = None,
    ) -> None:
        self._db = db
        self._storage = storage
        self._settings = settings or get_settings()
        self._gateway_factory = gateway_factory or (
            lambda: HttpMockShbClient(
                self._settings.mock_shb_base_url,
                self._settings.mock_shb_timeout_seconds,
            )
        )
        self._llm_factory = llm_factory or OpenAICompatibleStructuredLLM

    def execute(
        self,
        case_id: UUID,
        *,
        requested_by: str,
        idempotency_key: str | None = None,
    ) -> OperationExecutionResponse:
        stable_key = idempotency_key or f"case:{case_id}:approved:v1"
        case = self._db.scalar(
            select(Case).where(Case.id == case_id).with_for_update()
        )
        if case is None:
            raise LookupError(f"Case {case_id} was not found")
        approval = self._db.scalar(
            select(Approval).where(Approval.case_id == case_id)
        )
        if (
            approval is None
            or approval.decision != ApprovalDecision.APPROVED.value
            or case.status
            not in {CaseStatus.APPROVED.value, CaseStatus.COMPLETED.value}
        ):
            write_audit_log(
                self._db,
                case_id=case_id,
                actor_type="HUMAN",
                actor_id=requested_by,
                action="OPERATIONS_BLOCKED",
                entity_type="case",
                entity_id=str(case_id),
                outcome=AuditOutcome.BLOCKED,
                error="Explicit approved human decision is required",
            )
            self._db.commit()
            raise OperationsBlockedError(
                "Operations requires an explicit approved human decision"
            )

        execution = self._db.scalar(
            select(OperationExecution).where(
                OperationExecution.case_id == case_id
            )
        )
        if execution is not None and execution.status == OperationStatus.SUCCEEDED.value:
            return self._to_response(execution)
        if execution is not None and execution.status in {
            OperationStatus.PENDING.value,
            OperationStatus.RUNNING.value,
        }:
            raise OperationsInProgressError("Operations execution is already in progress")

        request_payload = {
            "case_id": str(case.id),
            "company_name": case.company_name,
            "requested_amount": str(case.requested_amount),
            "currency": case.currency,
            "human_decision": approval.decision,
            "verified_by": approval.verified_by,
        }
        if execution is None:
            execution = OperationExecution(
                case_id=case.id,
                idempotency_key=stable_key,
                status=OperationStatus.PENDING.value,
                request_payload=request_payload,
                artifact_keys=[],
            )
            self._db.add(execution)
            self._db.flush()
        else:
            execution.idempotency_key = stable_key
            execution.request_payload = request_payload
            execution.response_payload = None
            execution.artifact_keys = []
            execution.error_message = None

        execution.status = OperationStatus.RUNNING.value
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.BANKING_OPERATIONS.value,
            action="OPERATIONS_REQUESTED",
            entity_type="operation_execution",
            entity_id=str(execution.id),
            request=request_payload,
        )
        self._db.commit()

        try:
            response = self._execute_external_steps(case, approval)
            execution = self._db.get(OperationExecution, execution.id)
            case = self._db.get(Case, case.id)
            if execution is None or case is None:
                raise RuntimeError("Operations transaction state was lost")
            execution.status = OperationStatus.SUCCEEDED.value
            execution.response_payload = response
            execution.artifact_keys = [
                str(response["agreement_object_key"]),
                str(response["onboarding_object_key"]),
            ]
            execution.completed_at = datetime.now(timezone.utc)
            case.status = CaseStatus.COMPLETED.value
            write_audit_log(
                self._db,
                case_id=case.id,
                actor_type="AGENT",
                actor_id=AgentID.BANKING_OPERATIONS.value,
                action="OPERATIONS_COMPLETED",
                entity_type="operation_execution",
                entity_id=str(execution.id),
                response=response,
            )
            self._db.commit()
            return self._to_response(execution)
        except Exception as exc:
            self._db.rollback()
            execution = self._db.scalar(
                select(OperationExecution).where(
                    OperationExecution.case_id == case_id
                )
            )
            if execution is not None:
                execution.status = OperationStatus.FAILED.value
                execution.error_message = type(exc).__name__
                execution.completed_at = datetime.now(timezone.utc)
                write_audit_log(
                    self._db,
                    case_id=case_id,
                    actor_type="AGENT",
                    actor_id=AgentID.BANKING_OPERATIONS.value,
                    action="OPERATIONS_FAILED",
                    entity_type="operation_execution",
                    entity_id=str(execution.id),
                    outcome=AuditOutcome.FAILED,
                    error=type(exc).__name__,
                )
                self._db.commit()
            raise

    def _execute_external_steps(
        self,
        case: Case,
        approval: Approval,
    ) -> dict[str, object]:
        board = self._db.scalar(
            select(SharedBoard).where(SharedBoard.case_id == case.id)
        )
        if board is None or board.final_summary is None:
            raise OperationsBlockedError("A synthesized assessment is required")

        llm = self._llm_factory()
        agreement = llm.invoke_structured(
            schema=DraftAgreementContent,
            system_prompt=(
                "You are the Banking Operations Agent. Generate a non-binding draft "
                "credit agreement outline only after confirmed human approval. Use only "
                "the supplied case terms and assessment. Do not add rates, collateral, "
                "covenants, or customer obligations that are not present."
            ),
            user_prompt=json.dumps(
                {
                    "company_name": case.company_name,
                    "requested_amount": str(case.requested_amount),
                    "currency": case.currency,
                    "assessment": board.final_summary,
                    "human_decision": approval.decision,
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        gateway = self._gateway_factory()
        try:
            mock_response = gateway.create_onboarding_draft(
                MockOnboardingRequest(
                    case_id=case.id,
                    company_name=case.company_name,
                    requested_amount=case.requested_amount,
                    currency=case.currency,
                    human_decision=approval.decision,
                )
            )
        finally:
            close = getattr(gateway, "close", None)
            if callable(close):
                close()

        agreement_key = f"cases/{case.id}/operations/Draft_Credit_Agreement.pdf"
        onboarding_key = f"cases/{case.id}/operations/Core_Banking_Onboarding.json"
        pdf_payload = _render_agreement_pdf(case, agreement)
        onboarding_payload = json.dumps(
            mock_response.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        self._storage.put(
            bucket=self._settings.minio_case_bucket,
            object_key=agreement_key,
            data=io.BytesIO(pdf_payload),
            size_bytes=len(pdf_payload),
            content_type="application/pdf",
        )
        self._storage.put(
            bucket=self._settings.minio_case_bucket,
            object_key=onboarding_key,
            data=io.BytesIO(onboarding_payload),
            size_bytes=len(onboarding_payload),
            content_type="application/json",
        )
        return {
            **mock_response.model_dump(mode="json"),
            "agreement_object_key": agreement_key,
            "onboarding_object_key": onboarding_key,
        }

    def _to_response(
        self,
        execution: OperationExecution,
    ) -> OperationExecutionResponse:
        response_payload = execution.response_payload or {}
        artifacts = None
        if execution.status == OperationStatus.SUCCEEDED.value:
            agreement_key = str(response_payload["agreement_object_key"])
            artifacts = OperationArtifactResponse(
                agreement_id=str(response_payload["agreement_id"]),
                onboarding_id=str(response_payload["onboarding_id"]),
                request_id=str(response_payload["request_id"]),
                agreement_url=self._storage.presigned_get_url(
                    bucket=self._settings.minio_case_bucket,
                    object_key=agreement_key,
                    expires=timedelta(minutes=15),
                ),
            )
        return OperationExecutionResponse(
            id=execution.id,
            case_id=execution.case_id,
            status=execution.status,
            idempotency_key=execution.idempotency_key,
            artifacts=artifacts,
            created_at=execution.created_at,
            completed_at=execution.completed_at,
        )


def _render_agreement_pdf(case: Case, draft: DraftAgreementContent) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    del width
    text = pdf.beginText(48, height - 54)
    text.setFont("Helvetica-Bold", 15)
    text.textLine(draft.title)
    text.setFont("Helvetica", 10)
    text.textLine("")
    text.textLine(f"Borrower: {case.company_name}")
    text.textLine(
        f"Requested facility: {case.currency} {_format_amount(case.requested_amount)}"
    )
    text.textLine("")
    for line in _wrap_text(f"Purpose: {draft.purpose}"):
        text.textLine(line)
    text.textLine("")
    text.textLine("Preliminary terms:")
    for item in draft.preliminary_terms:
        for line in _wrap_text(f"- {item}"):
            text.textLine(line)
    if draft.conditions_precedent:
        text.textLine("")
        text.textLine("Conditions precedent:")
        for item in draft.conditions_precedent:
            for line in _wrap_text(f"- {item}"):
                text.textLine(line)
    text.textLine("")
    for line in _wrap_text(draft.disclaimer):
        text.textLine(line)
    pdf.drawText(text)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _wrap_text(value: str, width: int = 95) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _format_amount(value: Decimal) -> str:
    return f"{value:,.2f}"
