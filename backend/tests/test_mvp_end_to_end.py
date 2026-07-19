from __future__ import annotations

import json
import asyncio
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pydantic import BaseModel

from app.config import Settings
from app.main import app
from app.services.case_repository import CaseRepository
from app.services.llm import FPTLLMProvider, LLMProvider
from app.services.runtime import IncomeVerificationRuntime, get_runtime
from scripts.seed_synthetic_cases import _documents


HEADERS = {"X-Role": "UNDERWRITER", "X-Reviewer-Id": "test-underwriter"}


def build_runtime(tmp_path: Path) -> IncomeVerificationRuntime:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(
        database_url="sqlite://",
        document_storage_root=str(tmp_path / "documents"),
        fpt_api_key="",
        llm_model="",
    )
    repository = CaseRepository(session_factory=sessions, settings=settings)
    return IncomeVerificationRuntime(repository=repository, llm=LLMProvider())


def dossier_files(company: str = "Công ty Demo") -> dict[str, tuple[str, bytes, str]]:
    application = (
        f"Họ và tên: Nguyễn Văn Test\nĐơn vị công tác: {company}\n"
        "Thu nhập khai báo: 25000000 VND\nTiền tệ: VND\n"
    ).encode()
    contract = (
        f"Khách hàng: Nguyễn Văn Test\nCông ty: {company}\n"
        "Lương hợp đồng: 24000000 VND\nNgày hết hạn: 2028-12-31\n"
    ).encode()
    payslips = (
        f"Họ và tên: Nguyễn Văn Test\nCông ty: {company}\n" +
        "\n".join(f"2026-{month:02d} | base: 24000000 | bonus: 0" for month in range(1, 7))
    ).encode()
    statement = (
        "month,amount,source,description\n" +
        "\n".join(f"2026-{month:02d},25000000,{company},SALARY" for month in range(1, 7))
    ).encode()
    return {
        "LOAN_APPLICATION": ("application.txt", application, "text/plain"),
        "EMPLOYMENT_CONTRACT": ("contract.txt", contract, "text/plain"),
        "PAYSLIP_BUNDLE": ("payslips.txt", payslips, "text/plain"),
        "BANK_STATEMENT": ("statement.csv", statement, "text/csv"),
    }


def test_fpt_provider_calls_marketplace_and_validates_structured_json() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '```json\n{"value": "ok"}\n```'}}]},
        )

    class Output(BaseModel):
        value: str

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = FPTLLMProvider(
        api_key="competition-key",
        model_name="competition-model",
        client=client,
    )
    result = asyncio.run(
        provider.generate_structured(
            Output,
            system_prompt="Return structured data.",
            user_prompt="test",
            operation="test",
        )
    )
    asyncio.run(client.aclose())
    assert result.value == "ok"
    assert requests[0].url == "https://mkp-api.fptcloud.com/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer competition-key"
    assert json.loads(requests[0].content)["model"] == "competition-model"


def test_create_upload_run_reload_and_evidence(tmp_path: Path) -> None:
    runtime = build_runtime(tmp_path)
    app.dependency_overrides[get_runtime] = lambda: runtime
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/cases",
                headers=HEADERS,
                json={
                    "customer_name": "Nguyễn Văn Test",
                    "customer_code": "CIF-TEST-001",
                    "company": "Công ty Demo",
                    "requested_amount": 300000000,
                    "currency": "VND",
                },
            )
            assert created.status_code == 201
            case_id = created.json()["id"]
            for document_type, (name, content, content_type) in dossier_files().items():
                uploaded = client.post(
                    f"/api/v1/cases/{case_id}/documents",
                    headers=HEADERS,
                    data={"document_type": document_type},
                    files={"file": (name, content, content_type)},
                )
                assert uploaded.status_code == 201, uploaded.text

            run = client.post(f"/api/v1/cases/{case_id}/run", headers=HEADERS)
            assert run.status_code == 200, run.text
            context = run.json()
            assert context["workflow_state"] == "HUMAN_REVIEW"
            assert context["runtime_mode"] == "DETERMINISTIC_FALLBACK"
            assert context["income_analysis"]["average_income"] == "25000000"
            assert len(context["policy_result"]["citations"]) == 6
            assert len(context["evidence"]) >= 10

            detail = client.get(f"/api/v1/cases/{case_id}", headers=HEADERS)
            assert detail.status_code == 200
            assert detail.json()["context"]["workflow_state"] == "HUMAN_REVIEW"
            assert len(detail.json()["documents"]) == 4
            assert detail.json()["agent_runs"]
    finally:
        app.dependency_overrides.clear()


def test_synthetic_dataset_has_twenty_ground_truth_cases() -> None:
    path = Path(__file__).resolve().parents[2] / "dataset" / "synthetic_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len(cases) >= 20
    assert len({item["scenario"] for item in cases}) == len(cases)
    for item in cases:
        assert "expected_status" in item
        assert "expected_monthly_income" in item
        assert "expected_flags" in item
        assert "expected_missing_documents" in item


def test_first_ten_synthetic_cases_run_without_collection_or_pipeline_crash(tmp_path: Path) -> None:
    runtime = build_runtime(tmp_path)
    path = Path(__file__).resolve().parents[2] / "dataset" / "synthetic_cases.json"
    scenarios = json.loads(path.read_text(encoding="utf-8"))[:10]

    async def run_all() -> None:
        for item in scenarios:
            case_id = f"TEST-SYN-{int(item['case_no']):03d}"
            row = runtime.repository.create_case(
                case_id=case_id,
                application_id=f"TEST-APP-{int(item['case_no']):03d}",
                customer_name=item["customer_name"],
                customer_code=f"TEST-CIF-{int(item['case_no']):03d}",
                company=item["company"],
                requested_amount=300000000,
                currency=item.get("currency", "VND"),
            )
            omitted = set(item.get("omit", []))
            for document_type, (name, content) in _documents(item).items():
                if document_type in omitted:
                    continue
                runtime.repository.add_document(
                    case_id=row.id,
                    file_name=name,
                    content_type="text/csv" if name.endswith(".csv") else "text/plain",
                    document_type=document_type,
                    content=content,
                )
            result = await runtime.start_case(case_id, rerun=True)
            assert result.workflow_state != "TECHNICAL_ERROR"
            assert result.recommendation is not None
            if omitted:
                assert result.workflow_state == "AWAITING_DOCUMENTS"
            else:
                assert result.evidence

    asyncio.run(run_all())
