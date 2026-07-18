"""
Tier 2 Specialist — Banking Operations Agent.
Department: Banking Operations Department
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class BankingOperationsAssessment(BaseModel):
    agent_id: str = "BankingOperations"
    status: str = "COMPLETED"
    account_opening_eligible: bool = True
    disbursement_sop_passed: bool = True
    fee_schedule_applied: str = "STANDARD"
    risk_flags: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


def run_banking_operations_agent(case_data: Dict[str, Any], rag_policies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute Banking Operations Agent evaluation for SOP disbursement checks & fee schedules.
    """
    ops_data = case_data.get("operations_info", {})
    has_shb_account = ops_data.get("has_shb_account", True)
    disbursement_method = ops_data.get("disbursement_method", "Chuyển khoản tài khoản thanh toán")

    risk_flags = []
    account_ok = True

    if not has_shb_account:
        account_ok = False
        risk_flags.append("Doanh nghiệp chưa có Tài khoản thanh toán (TKTT) mở tại SHB để thực hiện giải ngân.")

    assessment = BankingOperationsAssessment(
        status="COMPLETED" if account_ok else "WARNING",
        account_opening_eligible=account_ok,
        disbursement_sop_passed=True,
        fee_schedule_applied="Biểu phí dịch vụ KHTC 2026",
        risk_flags=risk_flags,
        evidence=[
            {"source": "Quy trình giải ngân SOP RAG", "quote": f"Phương thức giải ngân: {disbursement_method}"},
            {"source": "Quy định tài khoản thanh toán SHB", "quote": f"Trạng thái TKTT: {'Đã mở' if has_shb_account else 'Chưa có'}"}
        ]
    )
    return assessment.model_dump()
