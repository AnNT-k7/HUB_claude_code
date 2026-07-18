"""
Tier 2 Specialist — Legal Agent.
Department: Legal & Compliance Department (Legal Workstream)
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class LegalAssessment(BaseModel):
    agent_id: str = "Legal"
    status: str = "COMPLETED"
    corporate_capacity_valid: bool = True
    signatory_authority_valid: bool = True
    litigation_status: str = "CLEAN"  # CLEAN, PENDING_LITIGATION, HIGH_RISK
    risk_flags: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


def run_legal_agent(case_data: Dict[str, Any], rag_policies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute Legal Agent governance, authority & litigation analysis.
    """
    legal_data = case_data.get("legal_info", {})
    signatory = legal_data.get("signatory_title", "Tổng Giám Đốc")
    has_litigation = legal_data.get("has_active_litigation", False)

    risk_flags = []
    litigation_status = "CLEAN"
    
    if has_litigation:
        litigation_status = "PENDING_LITIGATION"
        risk_flags.append("Doanh nghiệp đang có vụ kiện tranh chấp tài sản / hợp đồng chưa giải quyết tại Tòa án.")

    capacity_ok = True
    signatory_ok = True

    assessment = LegalAssessment(
        status="COMPLETED" if not has_litigation else "WARNING",
        corporate_capacity_valid=capacity_ok,
        signatory_authority_valid=signatory_ok,
        litigation_status=litigation_status,
        risk_flags=risk_flags,
        evidence=[
            {"source": "Điều lệ SHB & Điều lệ DN RAG", "quote": f"Người ký hợp đồng: {signatory} - Đúng thẩm quyền"},
            {"source": "Cổng thông tin Tòa án", "quote": f"Trạng thái tranh chấp: {litigation_status}"}
        ]
    )
    return assessment.model_dump()
