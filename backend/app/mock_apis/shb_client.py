from __future__ import annotations

from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.mock_apis.mock_endpoints import (
    MockOnboardingRequest,
    MockOnboardingResponse,
    build_mock_onboarding_response,
)


class MockShbGateway(Protocol):
    def create_onboarding_draft(
        self, request: MockOnboardingRequest
    ) -> MockOnboardingResponse: ...


class DeterministicMockShbGateway:
    """In-process deterministic adapter used by tests and demo execution."""

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

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpMockShbClient":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()
