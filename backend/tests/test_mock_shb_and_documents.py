from __future__ import annotations

import hashlib
from decimal import Decimal
from uuid import uuid4

import pytest

from app.mock_apis.mock_endpoints import (
    MockOnboardingRequest,
    build_mock_onboarding_response,
)
from app.mock_apis.shb_client import (
    DeterministicMockShbGateway,
    HttpMockShbClient,
)
from app.services.document_parser import DocumentValidationError, parse_document


def _onboarding_request(decision: str) -> MockOnboardingRequest:
    return MockOnboardingRequest(
        case_id=uuid4(),
        company_name="Cong ty Demo",
        requested_amount=Decimal("1000000"),
        currency="VND",
        human_decision=decision,
    )


def test_mock_shb_only_creates_a_draft_after_human_approval() -> None:
    request = _onboarding_request("APPROVED")
    gateway = DeterministicMockShbGateway()

    first = gateway.create_onboarding_draft(request)
    second = build_mock_onboarding_response(request)

    assert first == second
    assert first.status == "DRAFT_CREATED"
    assert first.agreement_id.startswith("DRAFT-")

    with pytest.raises(ValueError, match="approved human decision"):
        gateway.create_onboarding_draft(_onboarding_request("REJECTED"))


def test_http_mock_shb_client_rejects_non_local_or_non_mock_targets() -> None:
    with pytest.raises(ValueError, match="local mock-shb API"):
        HttpMockShbClient("https://api.real-bank.example/mock-shb")
    with pytest.raises(ValueError, match="local mock-shb API"):
        HttpMockShbClient("http://localhost:8000/real-shb")


def test_parse_json_document_returns_traceable_normalized_payload() -> None:
    payload = '{"company_name":"Công ty Ánh Dương","employees":42}'.encode()

    parsed = parse_document(payload, "application/json; charset=utf-8")

    assert parsed.sha256 == hashlib.sha256(payload).hexdigest()
    assert parsed.structured_payload == {
        "company_name": "Công ty Ánh Dương",
        "employees": 42,
    }
    assert "Công ty Ánh Dương" in parsed.extracted_text
    assert parsed.page_count is None


def test_parse_plain_text_document_preserves_utf8_text() -> None:
    payload = "Quy định tín dụng nội bộ".encode()

    parsed = parse_document(payload, "text/plain")

    assert parsed.extracted_text == "Quy định tín dụng nội bộ"
    assert parsed.structured_payload is None


@pytest.mark.parametrize(
    ("payload", "content_type", "message"),
    [
        (b"", "text/plain", "document is empty"),
        (b"[]", "application/json", "must contain an object"),
        (b"not-a-pdf", "application/pdf", "not a PDF"),
        (b"data", "application/zip", "unsupported content type"),
        (b"\xff", "text/plain", "must be UTF-8"),
    ],
)
def test_parse_document_fails_closed_for_invalid_content(
    payload: bytes, content_type: str, message: str
) -> None:
    with pytest.raises(DocumentValidationError, match=message):
        parse_document(payload, content_type)

