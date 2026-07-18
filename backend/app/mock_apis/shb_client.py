from __future__ import annotations

from typing import Protocol
from urllib.parse import quote, urlsplit

import httpx

from app.mock_apis.mock_endpoints import (
    MockComplianceResponse,
    MockCreditLedgerResponse,
    MockCustomerResponse,
    MockOnboardingRequest,
    MockOnboardingResponse,
    build_mock_onboarding_response,
)


class MockShbGateway(Protocol):
    def get_customer(self, customer_id: str) -> MockCustomerResponse: ...

    def get_credit_ledger(self, customer_id: str) -> MockCreditLedgerResponse: ...

    def get_compliance(self, customer_id: str) -> MockComplianceResponse: ...

    def create_onboarding_draft(
        self, request: MockOnboardingRequest
    ) -> MockOnboardingResponse: ...


class DeterministicMockShbGateway:
    """In-process deterministic adapter used by tests and demo execution."""

    def get_customer(self, customer_id: str) -> MockCustomerResponse:
        normalized = customer_id.strip().upper()
        return MockCustomerResponse(
            customer_id=normalized,
            company_name=f"Demo Company {normalized}",
            kyc_status="VERIFIED",
            active=True,
        )

    def get_credit_ledger(self, customer_id: str) -> MockCreditLedgerResponse:
        return MockCreditLedgerResponse(
            customer_id=customer_id.strip().upper(),
            total_exposure="0.00",
            delinquent=False,
        )

    def get_compliance(self, customer_id: str) -> MockComplianceResponse:
        normalized = customer_id.strip().upper()
        return MockComplianceResponse(
            customer_id=normalized,
            kyc_status="VERIFIED",
            aml_risk_level="LOW",
            sanctions_check_passed=True,
            regulatory_inquiry_open=False,
        )

    def create_onboarding_draft(
        self, request: MockOnboardingRequest
    ) -> MockOnboardingResponse:
        return build_mock_onboarding_response(request)


class HttpMockShbClient:
    """HTTP adapter that is deliberately restricted to configured mock hosts."""

    _ALLOWED_HOSTS = {"127.0.0.1", "localhost", "backend"}

    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        parsed = urlsplit(base_url)
        if parsed.hostname not in self._ALLOWED_HOSTS or not parsed.path.endswith(
            "/mock-shb"
        ):
            raise ValueError("Mock SHB URL must target the local mock-shb API")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    def create_onboarding_draft(
        self, request: MockOnboardingRequest
    ) -> MockOnboardingResponse:
        response = self._client.post(
            "/onboarding-drafts",
            json=request.model_dump(mode="json"),
        )
        response.raise_for_status()
        return MockOnboardingResponse.model_validate(response.json())

    def get_customer(self, customer_id: str) -> MockCustomerResponse:
        response = self._client.get(f"/customers/{quote(customer_id, safe='')}")
        response.raise_for_status()
        return MockCustomerResponse.model_validate(response.json())

    def get_credit_ledger(self, customer_id: str) -> MockCreditLedgerResponse:
        response = self._client.get(
            f"/credit-ledger/{quote(customer_id, safe='')}"
        )
        response.raise_for_status()
        return MockCreditLedgerResponse.model_validate(response.json())

    def get_compliance(self, customer_id: str) -> MockComplianceResponse:
        response = self._client.get(f"/compliance/{quote(customer_id, safe='')}")
        response.raise_for_status()
        return MockComplianceResponse.model_validate(response.json())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpMockShbClient":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()
