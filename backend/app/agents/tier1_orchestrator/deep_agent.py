"""
Tier 1 — Banking Orchestrator Deep Agent.

Responsibilities:
1. Intake loan applications.
2. Decompose tasks for Tier 2 specialists.
3. Orchestrate Tier 2 Shared Board pipeline.
4. Synthesize final results and push to Tier 3 / Human Review.
"""
from typing import Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from app.agents.tier2_board.tier2_pipeline import execute_tier2_pipeline

class TaskBreakdown(BaseModel):
    case_id: str
    required_departments: List[str]
    priority: str = "NORMAL"
    notes: str = ""

class SynthesizedAssessmentDraft(BaseModel):
    case_id: str
    status: str = "TIER3_PENDING_REVIEW"
    synthesis_summary: str
    tier2_execution_rounds: int
    tier2_specialists_run: List[str]
    missing_data_flags: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class BankingOrchestrator:
    def __init__(self):
        pass

    def plan_tasks(self, case_data: Dict[str, Any]) -> TaskBreakdown:
        """
        Analyze the incoming case data and determine which departments need to evaluate it.
        For a corporate loan, we generally need all 6 specialists.
        """
        print(f"[Orchestrator] Planning tasks for Case ID: {case_data.get('case_id', 'UNKNOWN')}")
        
        # Rule-based routing
        departments = [
            "CustomerRelationship", 
            "Credit", 
            "RiskManagement", 
            "Compliance", 
            "Legal", 
            "BankingOperations"
        ]
        
        if case_data.get("collateral_items"):
            departments.append("CollateralAppraisal")
            
        return TaskBreakdown(
            case_id=case_data.get("case_id", "UNKNOWN"),
            required_departments=departments,
            priority="HIGH" if case_data.get("requested_amount", 0) > 100_000_000_000 else "NORMAL"
        )

    def execute_workflow(self, case_data: Dict[str, Any]) -> SynthesizedAssessmentDraft:
        """
        Main entry point for Tier 1: Plan, Execute Tier 2, Synthesize.
        """
        case_id = case_data.get("case_id", "UNKNOWN")
        print(f"\n{'='*50}\n[Orchestrator] Starting Workflow for Case {case_id}\n{'='*50}")
        
        # 1. Plan Task Breakdown
        task_plan = self.plan_tasks(case_data)
        print(f"[Orchestrator] Task Plan: {task_plan.required_departments}")
        
        # 2. Dispatch to Tier 2 Pipeline
        print(f"\n[Orchestrator] Dispatching to Tier 2 Multi-Agent Pipeline...")
        final_board_state = execute_tier2_pipeline(case_data, max_rounds=3)
        
        # 3. Synthesize Results
        print(f"\n[Orchestrator] Synthesizing Tier 2 Results...")
        
        missing_data = []
        for agent_name, result in final_board_state.specialist_outputs.items():
            if hasattr(result, 'status') and result.status == "REQUIRES_MORE_DATA":
                missing_data.append(agent_name)
            elif isinstance(result, dict) and result.get("status") == "REQUIRES_MORE_DATA":
                missing_data.append(agent_name)
                
        if missing_data:
            synthesis_summary = f"Workflow halted. Missing data requested by: {', '.join(missing_data)}."
            status = "AWAITING_DOCS"
        elif final_board_state.status == "MAX_ROUNDS_REACHED":
            synthesis_summary = "Tier 2 completed but unresolved conflicts remain. Human intervention strictly required."
            status = "TIER3_PENDING_REVIEW"
        else:
            synthesis_summary = "Tier 2 consensus reached. Ready for operations processing pending Human Approval."
            status = "TIER3_PENDING_REVIEW"
            
        draft = SynthesizedAssessmentDraft(
            case_id=case_id,
            status=status,
            synthesis_summary=synthesis_summary,
            tier2_execution_rounds=final_board_state.current_round,
            tier2_specialists_run=list(final_board_state.specialist_outputs.keys()),
            missing_data_flags=missing_data
        )
        
        print(f"[Orchestrator] Final Status: {draft.status}")
        print(f"[Orchestrator] Summary: {draft.synthesis_summary}")
        
        return draft

# Global singleton
orchestrator = BankingOrchestrator()
