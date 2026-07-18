import sys
import os

# Ensure the backend directory is in sys.path so we can import app modules directly for local testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.api.v1.schemas import HumanReviewOutcome, ReviewRequest
from app.api.v1.income_verifications import MOCK_DB, start_workflow, get_case, submit_review
from app.api.v1.schemas import ProposedAction
from app.services.audit import get_audit_logs

import asyncio

async def run_test():
    print("=== TESTING PHASE 4 (REST API, ACTION EXECUTOR, AUDIT) ===\n")
    
    # 1. Start Workflow
    print("1. Starting Workflow for Application 'APP-999'")
    start_resp = await start_workflow("APP-999")
    case_id = start_resp.case_id
    print(f"-> Case ID created: {case_id}")
    print(f"-> Initial State: {start_resp.workflow_state}\n")
    
    # Simulate processing state change for testing review
    case = MOCK_DB[case_id]
    case.workflow_state = "PENDING_HUMAN_REVIEW"
    case.calculated_income.qualified_income = 23000000
    
    # Inject a proposed action
    action = ProposedAction(
        action_id="ACT-001",
        action_type="UPDATE_LOS",
        description="Update LOS with qualified income",
        requires_approval=True
    )
    action2 = ProposedAction(
        action_id="ACT-002",
        action_type="REQUEST_DOCUMENTS",
        description="Request missing pay stub",
        parameters={"missing_documents": ["Pay stub May 2026"]},
        requires_approval=True
    )
    action3 = ProposedAction(
        action_id="ACT-003",
        action_type="GENERATE_DOCUMENT",
        description="Generate official verification report",
        parameters={"template_name": "income_verification_report.md"},
        requires_approval=True
    )
    case.proposed_actions = [action, action2, action3]
    
    # 2. Get Case
    print("2. Fetching Case Context")
    fetched_case = await get_case(case_id)
    print(f"-> Workflow State: {fetched_case.workflow_state}")
    print(f"-> Proposed Actions count: {len(fetched_case.proposed_actions)}\n")
    
    # 3. Submit Review
    print("3. Submitting Human Review (APPROVE)")
    review_req = ReviewRequest(
        outcome=HumanReviewOutcome.APPROVED,
        reason="Looks good.",
        approved_action_ids=["ACT-001", "ACT-002", "ACT-003"],
        edited_qualified_income=23500000
    )
    review_resp = await submit_review(case_id, review_req)
    print(f"-> Review Message: {review_resp.message}")
    print(f"-> Next State: {review_resp.next_state}\n")
    
    # 4. Check Case State after Execution
    final_case = await get_case(case_id)
    print(f"4. Final Case State")
    print(f"-> Workflow State: {final_case.workflow_state}")
    print(f"-> Qualified Income (Updated by user): {final_case.calculated_income.qualified_income}\n")
    
    # 5. Print Audit Logs
    print("5. Audit Logs for Case")
    logs = get_audit_logs(case_id)
    for log in logs:
        print(f"  [{log['timestamp']}] {log['actor']} -> {log['event_type']}: {log['details']}")

if __name__ == "__main__":
    asyncio.run(run_test())
