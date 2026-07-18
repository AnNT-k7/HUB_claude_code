"""
Tier 2 Specialist — Customer Relationship Agent.
Department: Customer Relationship Department
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class CustomerRelationshipAssessment(BaseModel):
    agent_id: str = "CustomerRelationship"
    status: str = "COMPLETED"
    borrower_profile: Dict[str, Any] = Field(default_factory=dict)
    requested_loan_amount: float = 0.0
    loan_purpose: str = ""
    cic_status: str = "NORMAL"  # NORMAL, WARNING, BAD_CREDIT
    risk_flags: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


def run_customer_relationship_agent(case_data: Dict[str, Any], rag_policies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute Customer Relationship Agent analysis.
    """
    company_name = case_data.get("company_name", "Doanh nghiệp Vay")
    requested_amount = case_data.get("requested_amount", 0.0)
    purpose = case_data.get("loan_purpose", "Bổ sung vốn lưu động kinh doanh")
    cic_group = case_data.get("cic_group", 1)  # Group 1 = Normal

    risk_flags = []
    cic_status = "NORMAL"
    if cic_group > 2:
        cic_status = "BAD_CREDIT"
        risk_flags.append(f"Khách hàng có lịch sử nợ xấu nhóm {cic_group} tại CIC.")
    elif cic_group == 2:
        cic_status = "WARNING"
        risk_flags.append("Khách hàng có nợ cần chú ý (Nhóm 2) tại CIC.")

    assessment = CustomerRelationshipAssessment(
        status="COMPLETED" if cic_group <= 2 else "REQUIRES_MORE_DATA",
        borrower_profile={
            "company_name": company_name,
            "industry": case_data.get("industry", "Sản xuất / Thương mại"),
            "segment": case_data.get("segment", "SME"),
            "cic_group": cic_group
        },
        requested_loan_amount=requested_amount,
        loan_purpose=purpose,
        cic_status=cic_status,
        risk_flags=risk_flags,
        evidence=[
            {"source": "CIC Report", "quote": f"Nhóm nợ CIC: {cic_group}"},
            {"source": "Tờ trình đề xuất", "quote": f"Nhu cầu vay: {requested_amount:,.0f} VND - Mục đích: {purpose}"}
        ]
    )
    return assessment.model_dump()
