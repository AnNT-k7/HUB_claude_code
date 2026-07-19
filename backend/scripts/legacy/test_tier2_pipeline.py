import os
import sys
import json

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.tier2_board.tier2_pipeline import execute_tier2_pipeline

def run_test():
    print("==========================================================")
    print("Testing Tier 2 Multi-Agent Pipeline with 6 Specialists")
    print("==========================================================")

    # Mock Case Data representing a Corporate Loan Application
    mock_case_data = {
        "case_id": "case-shb-2026-001",
        "company_name": "Công ty Cổ phần Tập đoàn Dệt may Việt Á",
        "industry": "Sản xuất & Xuất khẩu Dệt may",
        "segment": "SME",
        "requested_amount": 150_000_000_000,  # 150 tỷ VND
        "loan_purpose": "Bổ sung vốn lưu động thu mua nguyên liệu dệt",
        "cic_group": 1,  # Group 1 = Normal
        "tax_code": "0101234567",
        "is_blacklisted": False,
        "privacy_consent": True,
        "financial_statements": {
            "net_operating_income": 35_000_000_000,  # 35 tỷ
            "total_debt_service": 25_000_000_000,    # 25 tỷ -> DSCR = 35 / 25 = 1.40x (OK >= 1.25x)
            "current_assets": 120_000_000_000,
            "current_liabilities": 80_000_000_000,   # Current Ratio = 1.5x
            "total_liabilities": 140_000_000_000,
            "total_equity": 60_000_000_000            # Leverage D/E = 140 / 60 = 2.33x (OK <= 3.0x)
        },
        "collateral_items": [
            {"type": "Bất động sản", "value": 200_000_000_000}, # 200 tỷ * 70% = 140 tỷ eligible -> LTV = 150/140 = 107% (FAIL > 70%)
        ],
        "legal_info": {
            "signatory_title": "Tổng Giám Đốc",
            "has_active_litigation": True  # Simulating active litigation to trigger Reviewer Debate!
        },
        "operations_info": {
            "has_shb_account": True,
            "disbursement_method": "Chuyển khoản tài khoản thanh toán"
        }
    }

    final_board = execute_tier2_pipeline(mock_case_data)

    print("\n==========================================================")
    print("FINAL SHARED BOARD SUMMARY RESULT")
    print("==========================================================")
    print(f"Status: {final_board.status}")
    print(f"Total Rounds Executed: {final_board.current_round}")
    print(f"Specialists Completed: {list(final_board.specialist_outputs.keys())}")
    
    print("\n--- DEBATE LOGS (Reviewer Quality Gate Findings) ---")
    for log in final_board.debate_logs:
        print(f"Round {log.round_number} | Critic: {log.critic_agent} -> Target: {log.target_agent}")
        print(f"  Error Identified: {log.error_identified.encode('ascii', 'ignore').decode()}")
        print(f"  Resolution Applied: {log.resolution_applied.encode('ascii', 'ignore').decode()}")

    output_path = os.path.join(os.path.dirname(__file__), "test_tier2_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_board.model_dump(), f, ensure_ascii=False, indent=2)

    print(f"\n[SUCCESS] Final Shared Board state saved to: {output_path}")

if __name__ == "__main__":
    run_test()
