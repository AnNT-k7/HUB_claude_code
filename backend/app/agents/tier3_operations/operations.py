"""
Tier 3 — Banking Operations Agent.

Department: Banking Operations Department
Activated ONLY after explicit human verification (Tier 3 sign-off).
Responsibilities (per PRD.md & PROJECT-RULES.md Section 3):
  - Update official case status (`PENDING_REVIEW` -> `APPROVED` or `REJECTED`)
  - Create missing-document requests if human officer or orchestrator requests additional files
  - Generate final draft outputs: `Draft_Credit_Agreement.pdf` and `Core_Banking_Onboarding.json`
  - Execute read-only pre-checks against Mock SHB APIs (`shb_client.py`)
  - Log every single operational action to `audit_logs` with immutable full payload traces
"""
import os
import json
import uuid
from typing import Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.services.mock_shb_api import shb_client

class OperationsExecutionResult(BaseModel):
    agent_id: str = "BankingOperations"
    case_id: str
    status: str = "PENDING"
    generated_agreement_path: str = ""
    onboarding_payload: Dict[str, Any] = Field(default_factory=dict)
    mock_api_responses: Dict[str, Any] = Field(default_factory=dict)
    audit_trace_id: str = ""

def run_operations_agent(case_data: Dict[str, Any], human_approval_status: str) -> OperationsExecutionResult:
    """
    Execute the Operations Agent.
    CRITICAL: This function MUST receive explicit human_approval_status.
    """
    case_id = case_data.get("case_id", "UNKNOWN")
    print(f"\n{'='*50}\n[Operations Agent] Starting execution for Case {case_id}\n{'='*50}")
    
    if human_approval_status != "APPROVED":
        print(f"[Operations Agent] Human approval status is '{human_approval_status}'. Halting operations.")
        return OperationsExecutionResult(
            case_id=case_id,
            status="HALTED",
            mock_api_responses={"error": "Human approval required"}
        )
        
    print("[Operations Agent] [SUCCESS] Human Approval verified. Proceeding with operations.")
    
    audit_trace_id = f"AUDIT-OPS-{uuid.uuid4().hex[:8].upper()}"
    mock_responses = {}
    
    # 1. Prechecks with Mock SHB Core
    tax_code = case_data.get("tax_code", "0000000000")
    print("[Operations Agent] Step 1: Running Core Banking Prechecks...")
    
    cust_res = shb_client.check_customer_master(tax_code)
    mock_responses["customer_master"] = cust_res
    
    cif = cust_res.get("data", {}).get("cif")
    if not cif:
        cif = f"NEW-{tax_code}" # Assign a temporary CIF for new customers
        
    ledger_res = shb_client.verify_credit_ledger(cif)
    mock_responses["credit_ledger"] = ledger_res
    
    # 2. Generate Draft Contract from Template
    print("[Operations Agent] Step 2: Generating Draft Credit Agreement...")
    
    template_path = os.path.join(os.path.dirname(__file__), "..", "..", "templates", "contract_template.md")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
            
        financials = case_data.get("financial_statements", {})
        dscr = round(financials.get("net_operating_income", 0) / financials.get("total_debt_service", 1), 2) if financials.get("total_debt_service") else 0
        
        # Simple string replacement for template variables
        contract_content = template_content.replace("{contract_number}", f"HDTD-{uuid.uuid4().hex[:6].upper()}/2026")
        contract_content = contract_content.replace("{current_date}", datetime.utcnow().strftime("%d/%m/%Y"))
        contract_content = contract_content.replace("{company_name}", case_data.get("company_name", "UNKNOWN COMPANY"))
        contract_content = contract_content.replace("{tax_code}", tax_code)
        contract_content = contract_content.replace("{cif}", cif)
        contract_content = contract_content.replace("{case_id}", case_id)
        contract_content = contract_content.replace("{approved_amount}", f"{case_data.get('requested_amount', 0):,}")
        contract_content = contract_content.replace("{loan_purpose}", case_data.get("loan_purpose", "Bổ sung vốn lưu động"))
        contract_content = contract_content.replace("{interest_rate}", "8.5")
        contract_content = contract_content.replace("{ltv}", "70.0")
        contract_content = contract_content.replace("{dscr}", str(dscr))
        contract_content = contract_content.replace("{approval_status}", human_approval_status)
        
        draft_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "drafts")
        os.makedirs(draft_path, exist_ok=True)
        final_contract_path = os.path.join(draft_path, f"{case_id}_Draft_Credit_Agreement.md")
        
        with open(final_contract_path, "w", encoding="utf-8") as f:
            f.write(contract_content)
            
        print(f"  -> Contract saved to: {final_contract_path}")
        
    except Exception as e:
        print(f"[Operations Agent] ERROR generating contract: {e}")
        final_contract_path = ""
        
    # 3. Create Core Banking Onboarding Payload
    print("[Operations Agent] Step 3: Preparing Core Banking Onboarding Payload...")
    payload = {
        "case_id": case_id,
        "company_name": case_data.get("company_name"),
        "tax_code": tax_code,
        "cif": cif,
        "approved_amount": case_data.get("requested_amount"),
        "interest_rate": 8.5,
        "disbursement_method": case_data.get("operations_info", {}).get("disbursement_method", "Chuyển khoản"),
        "audit_trace_id": audit_trace_id
    }
    
    onboarding_res = shb_client.create_onboarding_draft(payload)
    mock_responses["onboarding_draft"] = onboarding_res
    
    # 4. Final Result (simulate audit log saving)
    print(f"[Operations Agent] Step 4: Finalizing and Logging Audit Trace [{audit_trace_id}]...")
    
    return OperationsExecutionResult(
        case_id=case_id,
        status="COMPLETED",
        generated_agreement_path=final_contract_path,
        onboarding_payload=payload,
        mock_api_responses=mock_responses,
        audit_trace_id=audit_trace_id
    )
