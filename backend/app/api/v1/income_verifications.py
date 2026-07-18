"""Income-verification API backed by the typed workflow runtime."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.agents.income_verification.human_review import HumanReviewError
from app.agents.income_verification.state import CaseContext
from app.services.runtime import (
    IncomeVerificationRuntime,
    RuntimeCaseNotFound,
    UnsupportedDemoApplication,
    get_runtime,
)

from .schemas import (
    AuditListResponse,
    EvidenceListResponse,
    ResetResponse,
    ReviewRequest,
    ReviewResponse,
    StartWorkflowRequest,
    StartWorkflowResponse,
)


router = APIRouter(tags=["Income Verification"])


def require_underwriter(
    x_reviewer_id: Annotated[str | None, Header()] = None,
    x_role: Annotated[str | None, Header()] = None,
) -> str:
    """MVP header-based authorization boundary; replace with bank IAM in production."""

    if x_role != "UNDERWRITER" or not x_reviewer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Underwriter role and reviewer identity are required.",
        )
    return x_reviewer_id


RuntimeDependency = Annotated[IncomeVerificationRuntime, Depends(get_runtime)]
ReviewerDependency = Annotated[str, Depends(require_underwriter)]


@router.post(
    "/applications/{application_id}/income-verification",
    response_model=StartWorkflowResponse,
)
async def start_workflow(
    application_id: str,
    _payload: StartWorkflowRequest,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> StartWorkflowResponse:
    try:
        context = await runtime.start(application_id)
    except UnsupportedDemoApplication as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StartWorkflowResponse(
        case_id=context.case_id,
        workflow_state=context.workflow_state,
    )


@router.post(
    "/applications/{application_id}/income-verification/reset",
    response_model=ResetResponse,
)
async def reset_workflow(
    application_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> ResetResponse:
    try:
        await runtime.reset(application_id)
    except UnsupportedDemoApplication as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ResetResponse(application_id=application_id, status="RESET")


@router.get("/income-verifications/{case_id}", response_model=CaseContext)
async def get_case(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> CaseContext:
    try:
        return await runtime.get(case_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc


@router.post(
    "/income-verifications/{case_id}/review",
    response_model=ReviewResponse,
)
async def submit_review(
    case_id: str,
    review: ReviewRequest,
    reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> ReviewResponse:
    try:
        context = await runtime.review(case_id, review, reviewer_id=reviewer_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    except HumanReviewError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewResponse(case_id=case_id, workflow_state=context.workflow_state)


@router.post(
    "/income-verifications/{case_id}/retry-actions",
    response_model=ReviewResponse,
)
async def retry_actions(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> ReviewResponse:
    try:
        context = await runtime.retry_actions(case_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewResponse(case_id=case_id, workflow_state=context.workflow_state)


@router.get(
    "/income-verifications/{case_id}/evidence",
    response_model=EvidenceListResponse,
)
async def get_evidence(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> EvidenceListResponse:
    try:
        context = await runtime.get(case_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    return EvidenceListResponse(
        case_id=case_id,
        evidence=context.evidence,
    )


@router.get(
    "/income-verifications/{case_id}/audit",
    response_model=AuditListResponse,
)
async def get_audit(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> AuditListResponse:
    try:
        context = await runtime.get(case_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    return AuditListResponse(
        case_id=case_id,
        audit_events=context.audit_events,
    )
