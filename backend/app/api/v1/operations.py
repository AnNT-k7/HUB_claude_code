from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.tier3_operations.operations import (
    BankingOperationsAgent,
    OperationsBlockedError,
    OperationsInProgressError,
)
from app.api.dependencies import CurrentOfficer, ObjectStorageDependency
from app.db.models import Approval, AuditOutcome, Case, CaseStatus
from app.db.session import get_db
from app.schemas.api import (
    ApprovalResponse,
    HumanDecisionRequest,
    OperationExecutionResponse,
)
from app.services.audit import write_audit_log
from app.services.llm import LLMGenerationError


router = APIRouter(prefix="/operations", tags=["operations"])


@router.post(
    "/cases/{case_id}/decision",
    response_model=ApprovalResponse,
)
def record_human_decision(
    case_id: UUID,
    request: HumanDecisionRequest,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    case = db.scalar(select(Case).where(Case.id == case_id).with_for_update())
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    approval = db.scalar(select(Approval).where(Approval.case_id == case_id))
    target_status = CaseStatus(request.decision.value)
    if (
        approval is not None
        and case.status == target_status.value
        and approval.decision == request.decision.value
        and approval.feedback == request.feedback
        and approval.verified_by == officer.officer_id
    ):
        return _approval_response(approval)

    if case.status != CaseStatus.TIER3_PENDING_REVIEW.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A decision is only accepted at the human verification gate",
        )

    now = datetime.now(timezone.utc)
    if approval is None:
        approval = Approval(
            case_id=case_id,
            verified_by=officer.officer_id,
            decision=request.decision.value,
            feedback=request.feedback,
            decided_at=now,
        )
        db.add(approval)
        db.flush()
    else:
        approval.verified_by = officer.officer_id
        approval.decision = request.decision.value
        approval.feedback = request.feedback
        approval.decided_at = now

    case.status = target_status.value
    write_audit_log(
        db,
        case_id=case_id,
        actor_type="HUMAN",
        actor_id=officer.officer_id,
        action="HUMAN_DECISION_RECORDED",
        entity_type="approval",
        entity_id=str(approval.id),
        outcome=AuditOutcome.SUCCEEDED,
        request=request,
        response={"case_status": case.status},
    )
    db.commit()
    db.refresh(approval)
    return _approval_response(approval)


@router.post(
    "/cases/{case_id}/execute",
    response_model=OperationExecutionResponse,
)
def execute_approved_operations(
    case_id: UUID,
    officer: CurrentOfficer,
    storage: ObjectStorageDependency,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=255),
    ] = None,
    db: Session = Depends(get_db),
) -> OperationExecutionResponse:
    try:
        return BankingOperationsAgent(db, storage).execute(
            case_id,
            requested_by=officer.officer_id,
            idempotency_key=(idempotency_key or "").strip() or None,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        ) from exc
    except (OperationsBlockedError, OperationsInProgressError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except LLMGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider could not generate the operations draft",
        ) from exc


def _approval_response(approval: Approval) -> ApprovalResponse:
    return ApprovalResponse(
        id=approval.id,
        case_id=approval.case_id,
        verified_by=approval.verified_by,
        decision=approval.decision,
        feedback=approval.feedback,
        decided_at=approval.decided_at,
    )
