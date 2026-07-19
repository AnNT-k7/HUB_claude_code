import os
import sys
import json

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.tier1_orchestrator.deep_agent import orchestrator
from app.agents.tier3_operations.operations import run_operations_agent

def run_test():
    print("==========================================================")
    print("Testing Phase 4: Tier 1 Orchestrator -> Tier 3 Operations")
    print("==========================================================")

    # Mock Case Data
    mock_case_data = {
        "case_id": "case-shb-2026-002",
        "company_name": "Công ty Cổ phần Năng lượng Xanh Việt Nam",
        "industry": "Năng lượng tái tạo",
        "segment": "Corporate",
        "requested_amount": 250_000_000_000,  # 250 tỷ VND
        "loan_purpose": "Đầu tư dự án điện mặt trời áp mái",
        "cic_group": 1,
        "tax_code": "0109998887",
        "is_blacklisted": False,
        "privacy_consent": True,
        "financial_statements": {
            "net_operating_income": 45_000_000_000,
            "total_debt_service": 20_000_000_000,    # DSCR = 2.25x
            "current_assets": 180_000_000_000,
            "current_liabilities": 100_000_000_000,   # Current Ratio = 1.8x
            "total_liabilities": 200_000_000_000,
            "total_equity": 150_000_000_000           # Leverage D/E = 1.33x
        },
        "collateral_items": [
            {"type": "Hệ thống điện mặt trời", "value": 400_000_000_000}, # 400 tỷ * 70% = 280 tỷ eligible -> LTV = 250/280 = 89% (FAIL > 70%)
        ],
        "legal_info": {
            "signatory_title": "Chủ tịch HĐQT",
            "has_active_litigation": False
        },
        "operations_info": {
            "has_shb_account": False,
            "disbursement_method": "Chuyển khoản thanh toán cho nhà thầu EPC"
        }
    }

    # ==========================================
    # 1. TEST TIER 1 ORCHESTRATOR
    # ==========================================
    print("\n>>> 1. SIMULATING NEW LOAN APPLICATION (TIER 1) <<<")
    orchestrator_draft = orchestrator.execute_workflow(mock_case_data)
    
    print("\n==========================================================")
    print("ORCHESTRATOR SYNTHESIZED ASSESSMENT DRAFT")
    print("==========================================================")
    print(f"Status: {orchestrator_draft.status}")
    print(f"Summary: {orchestrator_draft.synthesis_summary}")
    
    # ==========================================
    # 2. TEST TIER 3 OPERATIONS (Simulate Human Approval)
    # ==========================================
    print("\n>>> 2. SIMULATING HUMAN APPROVAL & OPERATIONS (TIER 3) <<<")
    
    # Giả lập con người (Banking Officer) đã vào Dashboard đọc báo cáo và bấm "APPROVE"
    simulated_human_decision = "APPROVED"
    
    ops_result = run_operations_agent(mock_case_data, simulated_human_decision)
    
    print("\n==========================================================")
    print("OPERATIONS AGENT EXECUTION RESULT")
    print("==========================================================")
    print(f"Status: {ops_result.status}")
    print(f"Audit Trace ID: {ops_result.audit_trace_id}")
    print(f"Contract Path: {ops_result.generated_agreement_path}")
    
    print("\nMock Core Banking Responses:")
    print(json.dumps(ops_result.mock_api_responses, ensure_ascii=False, indent=2))
    
    output_path = os.path.join(os.path.dirname(__file__), "test_phase4_result.json")
    
    final_output = {
        "tier1_draft": orchestrator_draft.model_dump(),
        "tier3_operations": ops_result.model_dump()
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    print(f"\n[SUCCESS] Final Test Result saved to: {output_path}")

if __name__ == "__main__":
    run_test()
