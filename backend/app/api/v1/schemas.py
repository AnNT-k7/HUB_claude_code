"""Strict request/response contracts for the income-verification API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.income_verification.human_review import HumanReviewCommand
from app.agents.income_verification.state import AuditEvent, EvidenceCitation, WorkflowState


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateCaseRequest(ApiModel):
    customer_name: str = Field(min_length=1, max_length=200)
    customer_code: str | None = Field(default=None, min_length=1, max_length=100)
    company: str = Field(min_length=1, max_length=250)
    requested_amount: Decimal = Field(gt=0)
    currency: str = Field(default="VND", min_length=3, max_length=3)
    application_id: str | None = Field(default=None, min_length=1, max_length=100)


class DocumentResponse(ApiModel):
    id: str
    case_id: str
    file_name: str
    content_type: str
    document_type: str
    checksum: str
    size_bytes: int
    page_count: int | None
    processing_status: str
    error_message: str | None
    uploaded_at: datetime


class CaseSummaryResponse(ApiModel):
    id: str
    application_id: str
    customer_name: str
    customer_code: str
    company: str
    requested_amount: Decimal
    currency: str
    status: str
    pipeline_status: str
    state_version: int
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class CaseDetailResponse(CaseSummaryResponse):
    documents: list[DocumentResponse] = Field(default_factory=list)
    context: dict[str, object] | None = None
    agent_runs: list[dict[str, object]] = Field(default_factory=list)


class CaseListResponse(ApiModel):
    items: list[CaseSummaryResponse]
    total: int


class RuntimeInfoResponse(ApiModel):
    llm_provider: str
    llm_model: str
    llm_mode: str
    rag_mode: str
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    policy_corpus: str
    synthetic_policy_notice: str


class StartWorkflowRequest(ApiModel):
    pass


class StartWorkflowResponse(ApiModel):
    case_id: str
    workflow_state: WorkflowState


class ResetResponse(ApiModel):
    application_id: str
    status: str


class ReviewRequest(HumanReviewCommand):
    pass


class ReviewResponse(ApiModel):
    case_id: str
    workflow_state: WorkflowState


class EvidenceListResponse(ApiModel):
    case_id: str
    evidence: list[EvidenceCitation]


class AuditListResponse(ApiModel):
    case_id: str
    audit_events: list[AuditEvent]
