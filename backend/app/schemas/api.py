from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import ContractModel
from app.schemas.enums import (
    ApprovalDecision,
    CaseStatus,
    DocumentStatus,
    OperationStatus,
)
from app.schemas.tier2 import SharedBoardState


class CaseCreateRequest(ContractModel):
    company_name: str = Field(min_length=1, max_length=255)
    requested_amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    input_payload: dict[str, object] = Field(default_factory=dict)


class CaseSummaryResponse(ContractModel):
    id: UUID
    company_name: str
    requested_amount: Decimal
    currency: str
    status: CaseStatus
    workflow_id: str
    workflow_version: str
    created_at: datetime
    updated_at: datetime


class DocumentResponse(ContractModel):
    id: UUID
    case_id: UUID
    document_type: str
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    status: DocumentStatus
    created_at: datetime


class CaseDetailResponse(CaseSummaryResponse):
    input_payload: dict[str, object]
    documents: list[DocumentResponse] = Field(default_factory=list)


class AssessmentStartResponse(ContractModel):
    case_id: UUID
    status: CaseStatus
    board: SharedBoardState


class HumanDecisionRequest(ContractModel):
    decision: ApprovalDecision
    feedback: str | None = Field(default=None, max_length=4_000)

    @model_validator(mode="after")
    def require_revision_feedback(self) -> "HumanDecisionRequest":
        if self.decision == ApprovalDecision.REVISION_REQUESTED and not self.feedback:
            raise ValueError("Revision requests require feedback")
        return self


class ApprovalResponse(ContractModel):
    id: UUID
    case_id: UUID
    verified_by: str
    decision: ApprovalDecision
    feedback: str | None
    decided_at: datetime


class OperationArtifactResponse(ContractModel):
    agreement_id: str
    onboarding_id: str
    request_id: str
    agreement_url: str | None = None


class OperationExecutionResponse(ContractModel):
    id: UUID
    case_id: UUID
    status: OperationStatus
    idempotency_key: str
    artifacts: OperationArtifactResponse | None = None
    created_at: datetime
    completed_at: datetime | None = None


class PolicyIngestionResponse(ContractModel):
    policy_document_id: UUID
    chunks_created: int
    duplicate_chunks: int
