"""Deterministic LTV calculation and Collateral Appraisal assessment builder."""

from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.enums import AssessmentStatus, RiskSeverity
from app.schemas.evidence import CaseDocumentEvidence, MissingDataRequest, RiskFlag
from app.schemas.tier2 import (
    CollateralAppraisalAssessment,
    CollateralItem,
    CollateralPolicyThreshold,
)

LTV_QUANTUM = Decimal("0.0001")


class LtvCalculationError(ValueError):
    """Raised when LTV cannot be calculated from valid positive amounts."""


def calculate_ltv_ratio(
    requested_loan_amount: Decimal,
    total_eligible_collateral_value: Decimal,
) -> Decimal:
    if requested_loan_amount <= 0:
        raise LtvCalculationError("Requested loan amount must be greater than zero")
    if total_eligible_collateral_value <= 0:
        raise LtvCalculationError(
            "Total eligible collateral value must be greater than zero"
        )
    return (requested_loan_amount / total_eligible_collateral_value).quantize(
        LTV_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def assess_collateral(
    requested_loan_amount: Decimal | None,
    collateral_items: Sequence[CollateralItem],
    policy_threshold: CollateralPolicyThreshold | None,
    *,
    document_evidence: Sequence[CaseDocumentEvidence] = (),
) -> CollateralAppraisalAssessment:
    """Calculate LTV with eligible values and never infer missing valuations."""

    missing_data: list[MissingDataRequest] = []
    if requested_loan_amount is None:
        missing_data.append(
            MissingDataRequest(
                code="REQUESTED_LOAN_AMOUNT_MISSING",
                description="Requested loan amount is required to calculate LTV.",
                requested_document_types=["LOAN_APPLICATION"],
                requested_fields=["requested_loan_amount"],
            )
        )
    if not collateral_items:
        missing_data.append(
            MissingDataRequest(
                code="COLLATERAL_VALUATION_MISSING",
                description="At least one current collateral appraisal is required.",
                requested_document_types=["COLLATERAL_APPRAISAL"],
                requested_fields=["collateral_items", "eligible_value"],
            )
        )
    if missing_data:
        return CollateralAppraisalAssessment(
            status=AssessmentStatus.REQUIRES_MORE_DATA,
            requested_loan_amount=requested_loan_amount,
            collateral_items=list(collateral_items),
            missing_data=missing_data,
            document_evidence=list(document_evidence),
            rationale_summary="LTV was not calculated because required inputs are absent.",
        )

    assert requested_loan_amount is not None
    total_appraised = sum(
        (item.appraised_value for item in collateral_items),
        start=Decimal("0"),
    )
    total_eligible = sum(
        (item.eligible_value for item in collateral_items),
        start=Decimal("0"),
    )
    risk_flags: list[RiskFlag] = []
    try:
        ltv_ratio = calculate_ltv_ratio(requested_loan_amount, total_eligible)
    except LtvCalculationError as exc:
        ltv_ratio = None
        risk_flags.append(
            RiskFlag(
                code="LTV_DENOMINATOR_INVALID",
                severity=RiskSeverity.HIGH,
                summary=f"LTV cannot be calculated: {exc}.",
                requires_policy_citation=False,
            )
        )

    citations = list(policy_threshold.citations) if policy_threshold else []
    if policy_threshold is None:
        risk_flags.append(
            RiskFlag(
                code="COLLATERAL_POLICY_THRESHOLD_UNAVAILABLE",
                severity=RiskSeverity.HIGH,
                summary=(
                    "LTV cannot receive a policy conclusion without a cited threshold."
                ),
                requires_policy_citation=False,
            )
        )
    elif ltv_ratio is not None and ltv_ratio > policy_threshold.maximum_ltv_ratio:
        risk_flags.append(
            RiskFlag(
                code="LTV_ABOVE_POLICY",
                severity=RiskSeverity.HIGH,
                summary=(
                    f"LTV {ltv_ratio} exceeds the cited maximum "
                    f"{policy_threshold.maximum_ltv_ratio}."
                ),
                policy_citations=citations,
            )
        )

    status = (
        AssessmentStatus.MANUAL_REVIEW
        if ltv_ratio is None or policy_threshold is None
        else AssessmentStatus.SUCCESS
    )
    return CollateralAppraisalAssessment(
        status=status,
        requested_loan_amount=requested_loan_amount,
        collateral_items=list(collateral_items),
        total_collateral_value=total_appraised,
        total_eligible_value=total_eligible,
        computed_ltv_ratio=ltv_ratio,
        policy_threshold=policy_threshold,
        risk_flags=risk_flags,
        policy_citations=citations,
        document_evidence=list(document_evidence),
        rationale_summary=(
            "LTV uses requested amount divided by total eligible collateral value; "
            "no appraisal value was inferred."
        ),
    )


__all__ = [
    "CollateralAppraisalAssessment",
    "CollateralItem",
    "CollateralPolicyThreshold",
    "LtvCalculationError",
    "assess_collateral",
    "calculate_ltv_ratio",
]
