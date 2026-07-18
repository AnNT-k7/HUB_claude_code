"""Deterministic contract builder for the Customer Relationship specialist."""

from collections.abc import Sequence

from app.schemas.enums import AssessmentStatus
from app.schemas.evidence import AgentCitation, CaseDocumentEvidence, MissingDataRequest
from app.schemas.tier2 import (
    BorrowerProfile,
    CustomerRelationshipAssessment,
    RequestedLoanTerms,
)


def assess_customer_relationship(
    borrower_profile: BorrowerProfile | None,
    requested_terms: RequestedLoanTerms | None,
    *,
    document_evidence: Sequence[CaseDocumentEvidence] = (),
    policy_citations: Sequence[AgentCitation] = (),
) -> CustomerRelationshipAssessment:
    """Build a typed assessment without filling absent borrower information."""

    missing_data: list[MissingDataRequest] = []
    if borrower_profile is None:
        missing_data.append(
            MissingDataRequest(
                code="BORROWER_PROFILE_MISSING",
                description="Borrower profile and corporate registration data are required.",
                requested_document_types=["CORPORATE_PROFILE"],
                requested_fields=[
                    "company_name",
                    "registration_number",
                    "industry",
                    "business_model_summary",
                ],
            )
        )
    if requested_terms is None:
        missing_data.append(
            MissingDataRequest(
                code="REQUESTED_TERMS_MISSING",
                description="The signed loan request with requested terms is required.",
                requested_document_types=["LOAN_APPLICATION"],
                requested_fields=["requested_amount", "currency"],
            )
        )

    status = (
        AssessmentStatus.REQUIRES_MORE_DATA
        if missing_data
        else AssessmentStatus.SUCCESS
    )
    rationale = (
        "Required borrower information is incomplete; no values were inferred."
        if missing_data
        else "Borrower profile and requested loan terms were extracted from case evidence."
    )
    return CustomerRelationshipAssessment(
        status=status,
        borrower_profile=borrower_profile,
        requested_terms=requested_terms,
        policy_citations=list(policy_citations),
        document_evidence=list(document_evidence),
        missing_data=missing_data,
        rationale_summary=rationale,
    )


__all__ = [
    "BorrowerProfile",
    "CustomerRelationshipAssessment",
    "RequestedLoanTerms",
    "assess_customer_relationship",
]
