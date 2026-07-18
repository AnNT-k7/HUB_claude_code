"""
Tier 2 Specialist — Credit Agent.
Department: Credit Department
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from app.services.financial_calculator import evaluate_financial_health


class CreditAssessment(BaseModel):
    agent_id: str = "Credit"
    status: str = "COMPLETED"
    dscr: float = 0.0
    current_ratio: float = 0.0
    leverage_de: float = 0.0
    is_dscr_valid: bool = False
    is_leverage_valid: bool = False
    risk_flags: List[str] = Field(default_factory=list)
    calculation_notes: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


def run_credit_agent(case_data: Dict[str, Any], rag_policies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute Credit Agent financial statement evaluation using deterministic math engine.
    """
    fin = case_data.get("financial_statements", {})
    noi = fin.get("net_operating_income", 0.0)
    debt_service = fin.get("total_debt_service", 1.0)
    curr_assets = fin.get("current_assets", 0.0)
    curr_liab = fin.get("current_liabilities", 1.0)
    total_liab = fin.get("total_liabilities", 0.0)
    total_equity = fin.get("total_equity", 1.0)
    req_amount = case_data.get("requested_amount", 0.0)
    collateral_val = case_data.get("collateral_value", 0.0)

    # Deterministic math engine call
    eval_result = evaluate_financial_health(
        net_operating_income=noi,
        total_debt_service=debt_service,
        current_assets=curr_assets,
        current_liabilities=curr_liab,
        total_liabilities=total_liab,
        total_equity=total_equity,
        requested_loan_amount=req_amount,
        eligible_collateral_value=collateral_val
    )

    risk_flags = []
    if not eval_result.is_dscr_valid:
        risk_flags.append(f"DSCR {eval_result.dscr}x vi phạm quy định tối thiểu 1.25x.")
    if not eval_result.is_leverage_valid:
        risk_flags.append(f"Tỷ lệ D/E {eval_result.leverage_de}x vượt hạn mức an toàn 3.0x.")

    assessment = CreditAssessment(
        status="COMPLETED" if (eval_result.is_dscr_valid and eval_result.is_leverage_valid) else "WARNING",
        dscr=eval_result.dscr or 0.0,
        current_ratio=eval_result.current_ratio or 0.0,
        leverage_de=eval_result.leverage_de or 0.0,
        is_dscr_valid=eval_result.is_dscr_valid,
        is_leverage_valid=eval_result.is_leverage_valid,
        risk_flags=risk_flags,
        calculation_notes=eval_result.calculation_notes,
        evidence=[
            {"source": "Báo cáo tài chính", "quote": f"Doanh thu thuần / NOI: {noi:,.0f} VND"},
            {"source": "Quy chế tín dụng RAG", "quote": "Điều 1: DSCR tối thiểu >= 1.25x"}
        ]
    )
    return assessment.model_dump()
