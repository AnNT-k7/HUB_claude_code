from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from datetime import datetime
import uuid

from .schemas import (
    CaseContextResponse, 
    ReviewRequest, 
    ReviewResponse, 
    StartWorkflowResponse,
    WorkflowState,
    HumanReviewOutcome,
    ExtractedData,
    CalculatedIncome
)

# Mock Action Executor and Audit Service imports (we will build these next)
from app.services.action_executor import execute_approved_actions
from app.services.audit import log_event

router = APIRouter(prefix="/income-verifications", tags=["Income Verification"])

# Mock In-Memory Database
MOCK_DB: Dict[str, CaseContextResponse] = {}

@router.post("/applications/{application_id}", response_model=StartWorkflowResponse)
async def start_workflow(application_id: str):
    case_id = str(uuid.uuid4())
    
    # Initialize a dummy case context
    case_context = CaseContextResponse(
        case_id=case_id,
        application_id=application_id,
        workflow_state=WorkflowState.FETCHING_DOCUMENTS,
        extracted_data=ExtractedData(),
        calculated_income=CalculatedIncome(),
        findings=[],
        proposed_actions=[],
        evidence_list=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    MOCK_DB[case_id] = case_context
    log_event(case_id, "START_WORKFLOW", "system", f"Workflow started for app {application_id}")
    
    return StartWorkflowResponse(
        case_id=case_id,
        workflow_state=case_context.workflow_state
    )

@router.get("/{case_id}", response_model=CaseContextResponse)
async def get_case(case_id: str):
    if case_id not in MOCK_DB:
        raise HTTPException(status_code=404, detail="Case not found")
    return MOCK_DB[case_id]

@router.post("/{case_id}/review", response_model=ReviewResponse)
async def submit_review(case_id: str, review: ReviewRequest):
    if case_id not in MOCK_DB:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = MOCK_DB[case_id]
    
    if case.workflow_state != WorkflowState.PENDING_HUMAN_REVIEW:
        # For testing purposes, we allow it, but in reality we'd block it.
        pass

    log_event(
        case_id, 
        "HUMAN_REVIEW_SUBMITTED", 
        "underwriter", 
        f"Outcome: {review.outcome.value}, Reason: {review.reason}"
    )

    if review.outcome == HumanReviewOutcome.APPROVED:
        # Overwrite income if edited
        if review.edited_qualified_income is not None:
            case.calculated_income.qualified_income = review.edited_qualified_income
            
        case.workflow_state = WorkflowState.EXECUTING_ACTIONS
        
        # Trigger Action Executor synchronously for Phase 4 MVP
        # In reality, this would be passed to a background worker
        execute_approved_actions(case_id, review.approved_action_ids)
        
        # After execution, complete workflow
        case.workflow_state = WorkflowState.COMPLETED
        
    elif review.outcome == HumanReviewOutcome.REJECTED:
        case.workflow_state = WorkflowState.COMPLETED
        
    elif review.outcome == HumanReviewOutcome.REVISION_REQUESTED:
        case.workflow_state = WorkflowState.FETCHING_DOCUMENTS
        
    case.updated_at = datetime.utcnow()
    MOCK_DB[case_id] = case
    
    return ReviewResponse(
        message="Review submitted successfully",
        next_state=case.workflow_state.value
    )
