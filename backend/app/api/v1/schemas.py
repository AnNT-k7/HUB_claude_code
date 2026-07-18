"""Strict request/response contracts for the income-verification API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.agents.income_verification.human_review import HumanReviewCommand
from app.agents.income_verification.state import (
    AuditEvent,
    EvidenceCitation,
    WorkflowState,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartWorkflowRequest(ApiModel):
    pass


class StartWorkflowResponse(ApiModel):
    case_id: str
    workflow_state: WorkflowState


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
