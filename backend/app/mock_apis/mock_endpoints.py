from decimal import Decimal
from uuid import UUID, uuid5

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field


router = APIRouter(prefix="/mock-shb", tags=["mock-shb"])
_MOCK_NAMESPACE = UUID("4f3ee5ef-df66-4e16-a5ea-34eca49ecaea")


class MockCustomerResponse(BaseModel):
    customer_id: str
    company_name: str
    kyc_status: str
    active: bool


class MockCreditLedgerResponse(BaseModel):
    customer_id: str
    total_exposure: Decimal
    delinquent: bool


class MockComplianceResponse(BaseModel):
    customer_id: str
    kyc_status: str
    aml_risk_level: str
    sanctions_check_passed: bool
    regulatory_inquiry_open: bool


class MockOnboardingRequest(BaseModel):
    case_id: UUID
    company_name: str = Field(min_length=1, max_length=255)
    requested_amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    human_decision: str


class MockOnboardingResponse(BaseModel):
    request_id: str
    agreement_id: str
    onboarding_id: str
    status: str


def build_mock_onboarding_response(
    request: MockOnboardingRequest,
) -> MockOnboardingResponse:
    if request.human_decision != "APPROVED":
        raise ValueError("Mock onboarding requires an approved human decision")
    stable_id = uuid5(_MOCK_NAMESPACE, str(request.case_id)).hex[:16].upper()
    return MockOnboardingResponse(
        request_id=f"REQ-{stable_id}",
        agreement_id=f"DRAFT-{stable_id}",
        onboarding_id=f"ONB-{stable_id}",
        status="DRAFT_CREATED",
    )


@router.get("/customers/{customer_id}", response_model=MockCustomerResponse)
def get_customer(customer_id: str) -> MockCustomerResponse:
    if not customer_id.strip() or customer_id.upper().startswith("INVALID"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown mock customer",
        )
    suffix = customer_id.strip().upper()
    return MockCustomerResponse(
        customer_id=suffix,
        company_name=f"Demo Company {suffix}",
        kyc_status="VERIFIED",
        active=True,
    )


@router.get(
    "/credit-ledger/{customer_id}", response_model=MockCreditLedgerResponse
)
def get_credit_ledger(customer_id: str) -> MockCreditLedgerResponse:
    if not customer_id.strip() or customer_id.upper().startswith("INVALID"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown mock customer",
        )
    return MockCreditLedgerResponse(
        customer_id=customer_id.strip().upper(),
        total_exposure=Decimal("0.00"),
        delinquent=False,
    )


@router.get(
    "/compliance/{customer_id}",
    response_model=MockComplianceResponse,
)
def get_compliance(customer_id: str) -> MockComplianceResponse:
    normalized = customer_id.strip().upper()
    if not normalized or normalized.startswith("INVALID"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown mock customer",
        )
    return MockComplianceResponse(
        customer_id=normalized,
        kyc_status="VERIFIED",
        aml_risk_level="HIGH" if normalized.startswith("PEP") else "LOW",
        sanctions_check_passed=not normalized.startswith("SANCTION"),
        regulatory_inquiry_open=normalized.startswith("INQUIRY"),
    )


@router.post("/onboarding-drafts", response_model=MockOnboardingResponse)
def create_onboarding_draft(
    request: MockOnboardingRequest,
) -> MockOnboardingResponse:
    try:
        return build_mock_onboarding_response(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
