"""
Tier 2 Specialist — Collateral Appraisal Agent.
Department: Collateral Appraisal Department
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from app.services.financial_calculator import calculate_ltv


class CollateralAppraisalAssessment(BaseModel):
    agent_id: str = "CollateralAppraisal"
    status: str = "COMPLETED"
    total_collateral_value: float = 0.0
    eligible_collateral_value: float = 0.0
    ltv: float = 0.0
    is_ltv_valid: bool = True
    collateral_types: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


def run_collateral_appraisal_agent(case_data: Dict[str, Any], rag_policies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute Collateral Appraisal Agent valuation & LTV computation.
    """
    req_amount = case_data.get("requested_amount", 0.0)
    collaterals = case_data.get("collateral_items", [])
    
    total_val = sum(c.get("value", 0.0) for c in collaterals)
    # Apply standard haircut (e.g. Real Estate 70%, Machinery 50%)
    eligible_val = 0.0
    types = []
    
    for item in collaterals:
        ctype = item.get("type", "Bất động sản")
        val = item.get("value", 0.0)
        types.append(ctype)
        
        haircut = 0.70 if ctype == "Bất động sản" else 0.50
        eligible_val += val * haircut

    ltv = calculate_ltv(req_amount, eligible_val) or 0.0
    max_ltv_allowed = 70.0  # Policy threshold

    risk_flags = []
    is_ltv_ok = ltv <= max_ltv_allowed and ltv > 0

    if ltv > max_ltv_allowed:
        risk_flags.append(f"Tỷ lệ cho vay trên giá trị TSBĐ (LTV {ltv}%) vượt ngưỡng tối đa cho phép {max_ltv_allowed}%.")
    if not collaterals:
        risk_flags.append("Khoản vay không có tài sản bảo đảm thế chấp.")

    assessment = CollateralAppraisalAssessment(
        status="COMPLETED" if is_ltv_ok else "WARNING",
        total_collateral_value=total_val,
        eligible_collateral_value=eligible_val,
        ltv=ltv,
        is_ltv_valid=is_ltv_ok,
        collateral_types=types,
        risk_flags=risk_flags,
        evidence=[
            {"source": "Biên bản định giá TSBĐ", "quote": f"Tổng giá trị định giá: {total_val:,.0f} VND - Giá trị quy đổi: {eligible_val:,.0f} VND"},
            {"source": "Quy định LTV RAG", "quote": f"LTV tính toán: {ltv}% (Hạn mức max: {max_ltv_allowed}%)"}
        ]
    )
    return assessment.model_dump()
