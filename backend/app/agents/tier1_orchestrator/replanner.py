"""
Tier 1 — Orchestrator Replanner.

Responsible for handling "REQUIRES_MORE_DATA" interruptions from Tier 2.
"""
from typing import List
from pydantic import BaseModel

class MissingDocumentRequest(BaseModel):
    case_id: str
    missing_documents: List[str]
    request_reason: str
    target_agents: List[str]

class OrchestratorReplanner:
    def __init__(self):
        pass

    def generate_document_request(self, case_id: str, missing_data_flags: List[str]) -> MissingDocumentRequest:
        """
        Generate a structured request for the user/client to upload missing documents.
        """
        print(f"[Replanner] Handling missing data flags for Case {case_id}: {missing_data_flags}")
        
        docs_needed = []
        reason = "Tier 2 Specialists could not complete evaluation due to missing information."
        
        if "Credit" in missing_data_flags:
            docs_needed.append("Báo cáo tài chính đã kiểm toán năm gần nhất (Bản scan PDF)")
        if "Legal" in missing_data_flags:
            docs_needed.append("Giấy chứng nhận đăng ký doanh nghiệp (Bản cập nhật mới nhất)")
        if "CollateralAppraisal" in missing_data_flags:
            docs_needed.append("Giấy chứng nhận Quyền sử dụng đất hoặc Đăng ký phương tiện giao thông")
        if "Compliance" in missing_data_flags:
            docs_needed.append("Biểu mẫu KYC bổ sung (Đại diện pháp luật)")
            
        if not docs_needed:
            docs_needed.append("Vui lòng liên hệ RM để biết thêm chi tiết các tài liệu cần bổ sung.")
            
        return MissingDocumentRequest(
            case_id=case_id,
            missing_documents=docs_needed,
            request_reason=reason,
            target_agents=missing_data_flags
        )

# Global singleton
replanner = OrchestratorReplanner()
