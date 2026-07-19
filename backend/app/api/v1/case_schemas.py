"""Request/response contracts for the multi-case management API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field

from app.agents.income_verification.state import WorkflowState

from .schemas import ApiModel


class CreateCaseRequest(ApiModel):
    customer_name: str | None = None
    customer_code: str | None = None
    employer: str | None = None
    requested_amount: Decimal | None = Field(default=None, ge=0)
    loan_term_months: int | None = Field(default=None, ge=1)


class CreateCaseResponse(ApiModel):
    case_id: str
    application_id: str
    workflow_state: WorkflowState


class CaseSummaryResponse(ApiModel):
    case_id: str
    application_id: str
    customer_name: str | None
    employer: str | None
    requested_amount: Decimal | None
    loan_term_months: int | None
    workflow_state: str
    verification_status: str | None
    document_count: int
    created_at: datetime
    updated_at: datetime


class CaseListResponse(ApiModel):
    cases: list[CaseSummaryResponse]


class CaseStatusResponse(ApiModel):
    case_id: str
    workflow_state: WorkflowState
    state_version: int
    updated_at: datetime


class DocumentSummaryResponse(ApiModel):
    document_id: str
    file_name: str
    content_type: str
    document_type: str | None
    classification_method: str | None
    checksum: str
    size_bytes: int
    parse_status: str
    uploaded_at: datetime


class DocumentListResponse(ApiModel):
    case_id: str
    documents: list[DocumentSummaryResponse]


class UploadDocumentResponse(ApiModel):
    document: DocumentSummaryResponse


class SystemStatusResponse(ApiModel):
    """Surfaces whether the pipeline is running with a live LLM/RAG or in
    mock/degraded fallback mode — required so the UI never silently implies
    a real integration is active when it isn't."""

    model_config = ConfigDict(extra="forbid")

    llm_mode: str
    rag_mode: str
