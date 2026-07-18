"""
Tier 2 Pipeline — LangGraph Orchestration of 6 Specialists + Reviewer Debate Loop.

Orchestrates:
1. Parallel execution of 6 Specialist Agents.
2. Blackboard state update on SharedBoard.
3. Reviewer Agent audit & debate loop (max 3 rounds).
4. Returns final consensus or max-round SharedBoard state.
"""
from typing import Dict, Any
from app.agents.tier2_board.shared_board import SharedBoardState
from app.agents.tier2_board.specialists import (
    run_customer_relationship_agent,
    run_credit_agent,
    run_risk_management_agent,
    run_compliance_agent,
    run_legal_agent,
    run_collateral_appraisal_agent,
    run_banking_operations_agent,
)
from app.agents.tier2_board.reviewer import run_reviewer_agent


def execute_tier2_pipeline(case_data: Dict[str, Any], max_rounds: int = 3) -> SharedBoardState:
    """
    Executes the complete Tier 2 Multi-Agent Shared Board Pipeline.
    """
    case_id = str(case_data.get("case_id", "demo-case-001"))
    board = SharedBoardState(case_id=case_id, max_debate_rounds=max_rounds)

    while board.status in ["IN_PROGRESS", "DEBATE_IN_PROGRESS"]:
        print(f"\n--- Tier 2 Execution Round {board.current_round}/{board.max_debate_rounds} ---")
        
        # Determine which agents need to run (all on round 1, targeted on re-analysis)
        targets = board.reanalysis_targets if board.reanalysis_targets else [
            "CustomerRelationship", "Credit", "RiskManagement", 
            "Compliance", "Legal", "CollateralAppraisal", "BankingOperations"
        ]

        if "CustomerRelationship" in targets:
            print("  -> Running Customer Relationship Agent...")
            board.specialist_outputs["CustomerRelationship"] = run_customer_relationship_agent(case_data)
            
        if "Credit" in targets:
            print("  -> Running Credit Agent...")
            board.specialist_outputs["Credit"] = run_credit_agent(case_data)
            
        if "RiskManagement" in targets:
            print("  -> Running Risk Management Agent...")
            board.specialist_outputs["RiskManagement"] = run_risk_management_agent(case_data)
            
        if "Compliance" in targets:
            print("  -> Running Compliance Agent...")
            board.specialist_outputs["Compliance"] = run_compliance_agent(case_data)
            
        if "Legal" in targets:
            print("  -> Running Legal Agent...")
            board.specialist_outputs["Legal"] = run_legal_agent(case_data)
            
        if "CollateralAppraisal" in targets:
            print("  -> Running Collateral Appraisal Agent...")
            board.specialist_outputs["CollateralAppraisal"] = run_collateral_appraisal_agent(case_data)
            
        if "BankingOperations" in targets:
            print("  -> Running Banking Operations Agent...")
            board.specialist_outputs["BankingOperations"] = run_banking_operations_agent(case_data)

        # Run Reviewer Agent Gate
        print("  -> Running Reviewer Agent Quality Gate & Debate Check...")
        board, has_errors = run_reviewer_agent(board)

        if not has_errors:
            print("[SUCCESS] Consensus reached across all 6 Specialist Agents! No errors found.")
            break
        elif board.status == "MAX_ROUNDS_REACHED":
            print(f"[WARNING] Reached maximum debate rounds ({board.max_debate_rounds}). Stopping debate loop.")
            break
        else:
            print(f"[DEBATE] Reviewer found errors. Triggering Round {board.current_round} re-analysis for: {board.reanalysis_targets}")

    return board
