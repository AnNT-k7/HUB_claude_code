"""
Tier 2 Specialist — Risk Management Agent.
Department: Risk Management Department
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class RiskManagementAssessment(BaseModel):
    agent_id: str = "RiskManagement"
    status: str = "COMPLETED"
    risk_tier: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    industry_risk: str = "LOW"
    concentration_limit_ok: bool = True
    risk_flags: List[str] = Field(default_factory=list)
    mitigation_suggestions: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


def run_risk_management_agent(case_data: Dict[str, Any], rag_policies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute Risk Management Agent evaluation against industry risk factors & concentration limits.
    """
    industry = case_data.get("industry", "")
    requested_amount = case_data.get("requested_amount", 0.0)
    bank_capital_limit = 500_000_000_000  # 500 tỷ VND limit for single corporate

    risk_flags = []
    mitigations = []
    risk_tier = "LOW"
    concentration_ok = True

    if requested_amount > bank_capital_limit:
        concentration_ok = False
        risk_flags.append(f"Khoản vay {requested_amount:,.0f} VND vượt hạn mức cấp tín dụng tối đa cho 1 KH (500 tỷ).")
        risk_tier = "HIGH"

    high_risk_industries = ["Bất động sản nghỉ dưỡng", "Khai khoáng", "Tiền ảo / Đặt cược"]
    if any(h in industry for h in high_risk_industries):
        risk_flags.append(f"Ngành nghề kinh doanh '{industry}' thuộc danh mục hạn chế tín dụng / rủi ro cao.")
        risk_tier = "MEDIUM" if risk_tier != "HIGH" else "HIGH"
        mitigations.append("Yêu cầu bổ sung tài sản thế chấp là BĐS thanh khoản cao hoặc Bảo lãnh thanh toán ngân hàng.")

    assessment = RiskManagementAssessment(
        status="COMPLETED" if concentration_ok and risk_tier != "HIGH" else "WARNING",
        risk_tier=risk_tier,
        industry_risk="HIGH" if any(h in industry for h in high_risk_industries) else "LOW",
        concentration_limit_ok=concentration_ok,
        risk_flags=risk_flags,
        mitigation_suggestions=mitigations,
        evidence=[
            {"source": "Chính sách hạn mức tín dụng RAG", "quote": "Giới hạn cấp tín dụng đơn lẻ tối đa 500 tỷ VND"},
            {"source": "Danh mục rủi ro ngành", "quote": f"Ngành đánh giá: {industry}"}
        ]
    )
    return assessment.model_dump()
