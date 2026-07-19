"""HTTP-level tests for the multi-case management API (app/api/v1/cases.py).

Complements tests/test_synthetic_cases.py (which drives CaseService
directly): this file exercises the FastAPI request/response contract —
status codes, validation errors, multipart upload, and the full
create → upload → run → review → audit round trip through the real ASGI
app — with the CaseService dependency overridden to a network-free
instance (mock LLM + keyword-match policy retriever + isolated in-memory
SQLite), per docs/PROJECT-RULES.md §10.
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.services.case_document_store as case_document_store_module  # noqa: E402
import app.services.case_service as case_service_module  # noqa: E402
from app.db.case_models import CaseBase  # noqa: E402
from app.main import app  # noqa: E402
from app.services.case_service import CaseService, get_case_service  # noqa: E402
from app.services.llm_provider import MockLLMProvider  # noqa: E402
from app.services.runtime import EmbeddedDemoPolicyRetriever  # noqa: E402

HEADERS = {"X-Role": "UNDERWRITER", "X-Reviewer-Id": "underwriter-api-test"}


class CaseManagementApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._test_engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        CaseBase.metadata.create_all(bind=cls._test_engine)
        cls._test_session_local = sessionmaker(bind=cls._test_engine, autoflush=False, autocommit=False)
        cls._real_session_local = case_service_module.CaseSessionLocal
        case_service_module.CaseSessionLocal = cls._test_session_local

        cls._tmp_storage_dir = BACKEND_ROOT / "data" / "_test_case_management_api_documents"
        cls._tmp_storage_dir.mkdir(parents=True, exist_ok=True)
        cls._real_case_root = case_document_store_module._case_root
        case_document_store_module._case_root = lambda: cls._tmp_storage_dir

        cls._test_service = CaseService(
            llm=MockLLMProvider(), policy_retriever=EmbeddedDemoPolicyRetriever()
        )
        app.dependency_overrides[get_case_service] = lambda: cls._test_service
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.pop(get_case_service, None)
        case_service_module.CaseSessionLocal = cls._real_session_local
        case_document_store_module._case_root = cls._real_case_root
        import shutil

        shutil.rmtree(cls._tmp_storage_dir, ignore_errors=True)

    def test_requires_underwriter_identity(self) -> None:
        response = self.client.get("/api/v1/cases")
        self.assertEqual(response.status_code, 403)

    def test_create_list_and_fetch_case(self) -> None:
        create = self.client.post(
            "/api/v1/cases",
            json={"customer_name": "API Test Customer", "employer": "API Test Co", "loan_term_months": 12},
            headers=HEADERS,
        )
        self.assertEqual(create.status_code, 201)
        case_id = create.json()["case_id"]
        self.assertEqual(create.json()["workflow_state"], "OPEN_CASE")

        listing = self.client.get("/api/v1/cases", headers=HEADERS)
        self.assertEqual(listing.status_code, 200)
        case_ids = [c["case_id"] for c in listing.json()["cases"]]
        self.assertIn(case_id, case_ids)

        detail = self.client.get(f"/api/v1/cases/{case_id}", headers=HEADERS)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["case_id"], case_id)

    def test_unknown_case_returns_404(self) -> None:
        response = self.client.get("/api/v1/cases/IV-DOES-NOT-EXIST", headers=HEADERS)
        self.assertEqual(response.status_code, 404)

    def test_upload_rejects_unsupported_format(self) -> None:
        create = self.client.post("/api/v1/cases", json={"customer_name": "Upload Test"}, headers=HEADERS)
        case_id = create.json()["case_id"]
        response = self.client.post(
            f"/api/v1/cases/{case_id}/documents",
            headers=HEADERS,
            files={"file": ("malware.exe", io.BytesIO(b"not a real document"), "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 422)

    def test_full_flow_create_upload_run_review_audit(self) -> None:
        create = self.client.post(
            "/api/v1/cases",
            json={
                "customer_name": "Nguyễn Thị Đầy Đủ",
                "employer": "Công ty TNHH Đầy Đủ",
                "requested_amount": 150000000,
                "loan_term_months": 18,
            },
            headers=HEADERS,
        )
        case_id = create.json()["case_id"]

        loan_app = (
            "ĐƠN ĐỀ NGHỊ VAY VỐN TÍN CHẤP\n"
            "- Họ và tên: Nguyễn Thị Đầy Đủ\n"
            "- Thu nhập khai báo: 24.000.000 VND/tháng\n"
            "- Đơn vị công tác: Công ty TNHH Đầy Đủ\n"
        )
        contract = (
            "HỢP ĐỒNG LAO ĐỘNG\nĐiều 3: Lương cơ bản theo hợp đồng: 23.000.000 VND/tháng\n"
            "Điều 5: Ngày hết hạn: 31/12/2027\n"
        )
        statement_lines = ["SAO KÊ TÀI KHOẢN NGÂN HÀNG", "| Ngày | Nội dung | Nguồn | Số tiền |"]
        payslip_lines = ["BẢNG LƯƠNG", "| Tháng | Lương cơ bản | Phụ cấp | Khấu trừ | Thực nhận |"]
        for month in range(1, 7):
            statement_lines.append(f"| 05/{month:02d}/2026 | Luong thang {month} | Công ty TNHH Đầy Đủ | 24000000 |")
            payslip_lines.append(f"| 2026-{month:02d} | 23000000 | 800000 | 500000 | 23300000 |")
        statement = "\n".join(statement_lines) + "\n"
        payslip = "\n".join(payslip_lines) + "\n"

        for file_name, content in [
            ("loan_application.txt", loan_app),
            ("employment_contract.txt", contract),
            ("bank_statement.txt", statement),
            ("payslip.txt", payslip),
        ]:
            upload = self.client.post(
                f"/api/v1/cases/{case_id}/documents",
                headers=HEADERS,
                files={"file": (file_name, io.BytesIO(content.encode("utf-8")), "text/plain")},
            )
            self.assertEqual(upload.status_code, 200, upload.text)

        documents = self.client.get(f"/api/v1/cases/{case_id}/documents", headers=HEADERS)
        self.assertEqual(len(documents.json()["documents"]), 4)

        run = self.client.post(f"/api/v1/cases/{case_id}/run", headers=HEADERS)
        self.assertEqual(run.status_code, 200, run.text)
        result = run.json()
        self.assertEqual(result["workflow_state"], "HUMAN_REVIEW")
        self.assertGreater(len(result["evidence"]), 0)
        self.assertIsNotNone(result["recommendation"])

        evidence = self.client.get(f"/api/v1/cases/{case_id}/evidence", headers=HEADERS)
        self.assertEqual(evidence.status_code, 200)
        self.assertGreater(len(evidence.json()["evidence"]), 0)

        first_doc_id = documents.json()["documents"][0]["document_id"]
        download = self.client.get(f"/api/v1/cases/{case_id}/documents/{first_doc_id}/download", headers=HEADERS)
        self.assertEqual(download.status_code, 200)
        self.assertIn(b"Nguy", download.content)  # verbatim source bytes round-trip

        approved_action_ids = [a["action_id"] for a in result["proposed_actions"]]
        review = self.client.post(
            f"/api/v1/cases/{case_id}/review",
            json={
                "outcome": "ACCEPT_ACTIONS",
                "reason": "Đã kiểm tra evidence và policy citation.",
                "approved_action_ids": approved_action_ids,
            },
            headers=HEADERS,
        )
        self.assertEqual(review.status_code, 200, review.text)
        self.assertEqual(review.json()["workflow_state"], "COMPLETED")

        audit = self.client.get(f"/api/v1/cases/{case_id}/audit", headers=HEADERS)
        self.assertEqual(audit.status_code, 200)
        event_types = {event["event_type"] for event in audit.json()["audit_events"]}
        self.assertIn("CASE_CREATED", event_types)
        self.assertIn("HUMAN_REVIEW_RECORDED", event_types)
        self.assertIn("EXECUTION_VERIFIED", event_types)

        # Duplicate review must be rejected (idempotency / state-machine guard).
        duplicate = self.client.post(
            f"/api/v1/cases/{case_id}/review",
            json={"outcome": "ACCEPT_ACTIONS", "reason": "duplicate", "approved_action_ids": approved_action_ids},
            headers=HEADERS,
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_incomplete_case_routes_to_awaiting_documents(self) -> None:
        create = self.client.post("/api/v1/cases", json={"customer_name": "Thiếu Hồ Sơ"}, headers=HEADERS)
        case_id = create.json()["case_id"]
        self.client.post(
            f"/api/v1/cases/{case_id}/documents",
            headers=HEADERS,
            files={"file": ("loan_application.txt", io.BytesIO("Họ và tên: Thiếu Hồ Sơ\n".encode()), "text/plain")},
        )
        run = self.client.post(f"/api/v1/cases/{case_id}/run", headers=HEADERS)
        self.assertEqual(run.status_code, 200)
        self.assertIn(run.json()["workflow_state"], {"AWAITING_DOCUMENTS", "MANUAL_REVIEW_REQUIRED"})

    def test_system_status_reports_mode(self) -> None:
        response = self.client.get("/api/v1/cases/system/status", headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("MOCK", body["llm_mode"])
        self.assertIn(body["rag_mode"], {"DEGRADED_KEYWORD_MATCH", "INJECTED"})


if __name__ == "__main__":
    unittest.main()
