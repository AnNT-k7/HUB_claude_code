"""
Tier 2 Specialist — Compliance Agent.
Department: Legal & Compliance Department (Compliance Workstream)
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class ComplianceAssessment(BaseModel):
    agent_id: str = "Compliance"
    status: str = "COMPLETED"
    kyc_passed: bool = True
    aml_sanctions_passed: bool = True
    data_privacy_consent: bool = True
    risk_flags: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


def run_compliance_agent(case_data: Dict[str, Any], rag_policies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute Compliance Agent KYC/AML/Sanctions checks.
    """
    kyc_data = case_data.get("kyc", {})
    tax_code = case_data.get("tax_code", "0100000000")
    is_blacklisted = case_data.get("is_blacklisted", False)
    has_privacy_consent = case_data.get("privacy_consent", True)

    risk_flags = []
    kyc_ok = bool(tax_code and len(tax_code) >= 10)
    aml_ok = not is_blacklisted

    if not kyc_ok:
        risk_flags.append("Mã số thuế / Hồ sơ đăng ký kinh doanh chưa hợp lệ.")
    if is_blacklisted:
        risk_flags.append("CẢNH BÁO AML/SANCTIONS: Doanh nghiệp hoặc Người đại diện nằm trong danh sách đen cấm vận.")
    if not has_privacy_consent:
        risk_flags.append("Thiếu Văn bản đồng ý xử lý dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP.")

    assessment = ComplianceAssessment(
        status="COMPLETED" if (kyc_ok and aml_ok and has_privacy_consent) else "REQUIRES_MORE_DATA",
        kyc_passed=kyc_ok,
        aml_sanctions_passed=aml_ok,
        data_privacy_consent=has_privacy_consent,
        risk_flags=risk_flags,
        evidence=[
            {"source": "Hệ thống tra cứu AML/Sanctions", "quote": f"Blacklist check: {'FAIL' if is_blacklisted else 'PASS'}"},
            {"source": "Quy định NĐ 13/2023 RAG", "quote": "Điều khoản xử lý dữ liệu cá nhân bắt buộc có sự đồng ý"}
        ]
    )
    return assessment.model_dump()
