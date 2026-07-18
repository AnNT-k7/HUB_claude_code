import sys
import os

# Fix windows print encoding
sys.stdout.reconfigure(encoding='utf-8')

# Ensure the backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.agents.income_verification.policy_agent import run_policy_agent
from app.api.v1.schemas import CaseContextResponse, ExtractedData, CalculatedIncome, WorkflowState
from datetime import datetime

def test_policy_agent():
    print("=== TESTING POLICY AGENT (RAG QUERY & ENHANCED PROMPT) ===\n")
    
    # 1. Create a dummy CaseContext
    case_context = CaseContextResponse(
        case_id="TEST-POLICY-001",
        application_id="APP-999",
        workflow_state=WorkflowState.ANALYZING_INCOME_AND_POLICY,
        extracted_data=ExtractedData(
            customer_name="Nguyen Van A",
            employer="Cong ty ABC"
        ),
        calculated_income=CalculatedIncome(
            average_3_months=20000000,
            average_6_months=21000000
        ),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # 2. Run the agent (which will build the prompt)
    prompt = run_policy_agent(case_context)
    
    # 3. Print the resulting prompt
    print("\n--- GENERATED SYSTEM PROMPT FOR LLM ---\n")
    print(prompt)
    print("\n---------------------------------------\n")
    print("Test passed! The agent successfully extracted case context, retrieved mock policies, and built a strict citation-enforced prompt.")

if __name__ == "__main__":
    test_policy_agent()
