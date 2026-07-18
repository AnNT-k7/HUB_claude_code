"""
Tier 2 Reviewer Agent — Debate & Cross-Checking Engine.

Inspects the Shared Board outputs across 6 Specialist Agents:
- Re-verifies mathematical calculations (DSCR, LTV, Leverage).
- Audits cross-department contradictions (e.g. Credit claims low risk while Legal reports active litigation).
- Generates DebateLog critiques and instructs target agents to re-evaluate.
- Enforces max_debate_rounds (default: 3) termination logic.
"""
from typing import Dict, Any, List, Tuple
from app.agents.tier2_board.shared_board import SharedBoardState, DebateLog


def run_reviewer_agent(board_state: SharedBoardState) -> Tuple[SharedBoardState, bool]:
    """
    Inspects SharedBoardState and returns (updated_board_state, has_critical_errors).
    """
    outputs = board_state.specialist_outputs
    current_round = board_state.current_round
    reanalysis_targets = []
    has_errors = False

    cr_out = outputs.get("CustomerRelationship", {})
    credit_out = outputs.get("Credit", {})
    risk_out = outputs.get("RiskManagement", {})
    comp_out = outputs.get("Compliance", {})
    legal_out = outputs.get("Legal", {})
    collateral_out = outputs.get("CollateralAppraisal", {})
    ops_out = outputs.get("BankingOperations", {})

    # Rule 1: Cross-check Legal Litigation vs Credit Status
    if legal_out.get("litigation_status") == "PENDING_LITIGATION" and credit_out.get("status") == "COMPLETED":
        has_errors = True
        reanalysis_targets.append("Credit")
        log = DebateLog(
            round_number=current_round,
            critic_agent="ReviewerAgent",
            target_agent="Credit",
            error_identified="Mâu thuẫn phòng ban: Legal Agent phát hiện doanh nghiệp đang có tranh chấp Tòa án, nhưng Credit Agent vẫn đánh giá loại COMPLETED.",
            resolution_applied="Yêu cầu Credit Agent đánh giá lại mức độ rủi ro tín dụng khi có tranh chấp pháp lý."
        )
        board_state.debate_logs.append(log)

    # Rule 2: Cross-check Compliance Blacklist vs Risk Management Tier
    if not comp_out.get("aml_sanctions_passed", True) and risk_out.get("risk_tier") != "CRITICAL":
        has_errors = True
        reanalysis_targets.append("RiskManagement")
        log = DebateLog(
            round_number=current_round,
            critic_agent="ReviewerAgent",
            target_agent="RiskManagement",
            error_identified="Mâu thuẫn phòng ban: Compliance Agent phát hiện vi phạm danh sách đen AML/Sanctions, nhưng Risk Management Agent đặt rủi ro dưới mức CRITICAL.",
            resolution_applied="Yêu cầu Risk Management Agent điều chỉnh phân cấp rủi ro lên CRITICAL."
        )
        board_state.debate_logs.append(log)

    # Rule 3: Re-verify Credit DSCR math
    dscr = credit_out.get("dscr", 0.0)
    is_dscr_valid = credit_out.get("is_dscr_valid", False)
    if dscr > 0 and dscr < 1.25 and is_dscr_valid:
        has_errors = True
        reanalysis_targets.append("Credit")
        log = DebateLog(
            round_number=current_round,
            critic_agent="ReviewerAgent",
            target_agent="Credit",
            error_identified=f"Lỗi tính toán: DSCR đạt {dscr}x < 1.25x nhưng lại gắn cờ is_dscr_valid = True.",
            resolution_applied="Sửa lại cờ validation DSCR thành False và thêm rủi ro vi phạm quy định."
        )
        board_state.debate_logs.append(log)

    # Rule 4: Re-verify Collateral LTV math
    ltv = collateral_out.get("ltv", 0.0)
    is_ltv_valid = collateral_out.get("is_ltv_valid", True)
    if ltv > 70.0 and is_ltv_valid:
        has_errors = True
        reanalysis_targets.append("CollateralAppraisal")
        log = DebateLog(
            round_number=current_round,
            critic_agent="ReviewerAgent",
            target_agent="CollateralAppraisal",
            error_identified=f"Lỗi tính toán: Tỷ lệ LTV đạt {ltv}% > 70.0% nhưng lại gắn cờ is_ltv_valid = True.",
            resolution_applied="Sửa lại cờ validation LTV thành False."
        )
        board_state.debate_logs.append(log)

    # Update Board State
    board_state.reanalysis_targets = list(set(reanalysis_targets))
    
    if not has_errors:
        board_state.status = "CONSENSUS_REACHED"
    elif board_state.is_round_limit_reached():
        board_state.status = "MAX_ROUNDS_REACHED"
    else:
        board_state.status = "DEBATE_IN_PROGRESS"
        board_state.current_round += 1

    return board_state, has_errors
