"""Deterministic credit metrics and typed Credit Agent assessment builder."""

from collections.abc import Callable, Sequence
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.enums import AssessmentStatus, RiskSeverity
from app.schemas.evidence import CaseDocumentEvidence, MissingDataRequest, RiskFlag
from app.schemas.tier2 import (
    CreditAssessment,
    CreditFinancialInputs,
    CreditPolicyThresholds,
    CreditRatios,
)

RATIO_QUANTUM = Decimal("0.0001")


class RatioCalculationError(ValueError):
    """Raised when a financial ratio cannot be calculated faithfully."""


def _quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_dscr(
    cash_available_for_debt_service: Decimal,
    principal_due: Decimal,
    interest_due: Decimal,
) -> Decimal:
    debt_service = principal_due + interest_due
    if debt_service <= 0:
        raise RatioCalculationError("Debt service must be greater than zero")
    return _quantize_ratio(cash_available_for_debt_service / debt_service)


def calculate_current_ratio(
    current_assets: Decimal,
    current_liabilities: Decimal,
) -> Decimal:
    if current_liabilities <= 0:
        raise RatioCalculationError("Current liabilities must be greater than zero")
    return _quantize_ratio(current_assets / current_liabilities)


def calculate_debt_to_equity(total_debt: Decimal, total_equity: Decimal) -> Decimal:
    if total_equity <= 0:
        raise RatioCalculationError("Total equity must be greater than zero")
    return _quantize_ratio(total_debt / total_equity)


def _missing_financial_data(
    inputs: CreditFinancialInputs,
) -> list[MissingDataRequest]:
    required_fields = (
        "cash_available_for_debt_service",
        "principal_due",
        "interest_due",
        "current_assets",
        "current_liabilities",
        "total_debt",
        "total_equity",
    )
    missing_fields = [
        field_name
        for field_name in required_fields
        if getattr(inputs, field_name) is None
    ]
    if not missing_fields:
        return []
    return [
        MissingDataRequest(
            code="FINANCIAL_INPUTS_MISSING",
            description=(
                "Audited financial inputs required for credit ratios are missing; "
                "the values will not be imputed."
            ),
            requested_document_types=[
                "AUDITED_FINANCIAL_STATEMENTS",
                "DEBT_SERVICE_SCHEDULE",
            ],
            requested_fields=missing_fields,
        )
    ]


def _safe_ratio(
    calculation: Callable[[], Decimal],
    *,
    code: str,
    summary: str,
    risk_flags: list[RiskFlag],
) -> Decimal | None:
    try:
        return calculation()
    except RatioCalculationError as exc:
        risk_flags.append(
            RiskFlag(
                code=code,
                severity=RiskSeverity.HIGH,
                summary=f"{summary}: {exc}.",
                requires_policy_citation=False,
            )
        )
        return None


def assess_credit(
    financial_inputs: CreditFinancialInputs | None,
    policy_thresholds: CreditPolicyThresholds | None,
    *,
    document_evidence: Sequence[CaseDocumentEvidence] = (),
    acknowledged_cross_domain_risks: Sequence[str] = (),
) -> CreditAssessment:
    """Calculate credit ratios and compare only against cited policy thresholds."""

    if financial_inputs is None:
        missing_data = [
            MissingDataRequest(
                code="FINANCIAL_STATEMENTS_MISSING",
                description="Audited financial statements are required for credit analysis.",
                requested_document_types=["AUDITED_FINANCIAL_STATEMENTS"],
                requested_fields=[
                    "cash_available_for_debt_service",
                    "principal_due",
                    "interest_due",
                    "current_assets",
                    "current_liabilities",
                    "total_debt",
                    "total_equity",
                ],
            )
        ]
        return CreditAssessment(
            status=AssessmentStatus.REQUIRES_MORE_DATA,
            missing_data=missing_data,
            document_evidence=list(document_evidence),
            acknowledged_cross_domain_risks=list(
                acknowledged_cross_domain_risks
            ),
            rationale_summary=(
                "Credit ratios were not calculated because required statements are absent."
            ),
        )

    missing_data = _missing_financial_data(financial_inputs)
    if missing_data:
        return CreditAssessment(
            status=AssessmentStatus.REQUIRES_MORE_DATA,
            financial_inputs=financial_inputs,
            missing_data=missing_data,
            document_evidence=list(document_evidence),
            acknowledged_cross_domain_risks=list(
                acknowledged_cross_domain_risks
            ),
            rationale_summary=(
                "Credit ratios were not calculated because required values are absent."
            ),
        )

    # The missing-data guard above narrows these values for human readers; asserts
    # also prevent a future contract change from silently introducing guesses.
    cash_available = financial_inputs.cash_available_for_debt_service
    principal_due = financial_inputs.principal_due
    interest_due = financial_inputs.interest_due
    current_assets = financial_inputs.current_assets
    current_liabilities = financial_inputs.current_liabilities
    total_debt = financial_inputs.total_debt
    total_equity = financial_inputs.total_equity
    assert cash_available is not None
    assert principal_due is not None
    assert interest_due is not None
    assert current_assets is not None
    assert current_liabilities is not None
    assert total_debt is not None
    assert total_equity is not None

    risk_flags: list[RiskFlag] = []
    dscr = _safe_ratio(
        lambda: calculate_dscr(cash_available, principal_due, interest_due),
        code="DSCR_DENOMINATOR_INVALID",
        summary="DSCR cannot be calculated",
        risk_flags=risk_flags,
    )
    current_ratio = _safe_ratio(
        lambda: calculate_current_ratio(current_assets, current_liabilities),
        code="CURRENT_RATIO_DENOMINATOR_INVALID",
        summary="Current Ratio cannot be calculated",
        risk_flags=risk_flags,
    )
    debt_to_equity = _safe_ratio(
        lambda: calculate_debt_to_equity(total_debt, total_equity),
        code="LEVERAGE_DENOMINATOR_INVALID",
        summary="Debt-to-Equity cannot be calculated",
        risk_flags=risk_flags,
    )
    calculated_ratios = CreditRatios(
        dscr=dscr,
        current_ratio=current_ratio,
        debt_to_equity=debt_to_equity,
    )

    citations = list(policy_thresholds.citations) if policy_thresholds else []
    if policy_thresholds is None:
        risk_flags.append(
            RiskFlag(
                code="CREDIT_POLICY_THRESHOLD_UNAVAILABLE",
                severity=RiskSeverity.HIGH,
                summary=(
                    "Ratios were calculated, but no cited credit policy threshold "
                    "was supplied for a policy conclusion."
                ),
                requires_policy_citation=False,
            )
        )
    else:
        if (
            dscr is not None
            and policy_thresholds.minimum_dscr is not None
            and dscr < policy_thresholds.minimum_dscr
        ):
            risk_flags.append(
                RiskFlag(
                    code="DSCR_BELOW_POLICY",
                    severity=RiskSeverity.HIGH,
                    summary=(
                        f"DSCR {dscr} is below the cited minimum "
                        f"{policy_thresholds.minimum_dscr}."
                    ),
                    policy_citations=citations,
                )
            )
        if (
            current_ratio is not None
            and policy_thresholds.minimum_current_ratio is not None
            and current_ratio < policy_thresholds.minimum_current_ratio
        ):
            risk_flags.append(
                RiskFlag(
                    code="CURRENT_RATIO_BELOW_POLICY",
                    severity=RiskSeverity.MEDIUM,
                    summary=(
                        f"Current Ratio {current_ratio} is below the cited minimum "
                        f"{policy_thresholds.minimum_current_ratio}."
                    ),
                    policy_citations=citations,
                )
            )
        if (
            debt_to_equity is not None
            and policy_thresholds.maximum_debt_to_equity is not None
            and debt_to_equity > policy_thresholds.maximum_debt_to_equity
        ):
            risk_flags.append(
                RiskFlag(
                    code="LEVERAGE_ABOVE_POLICY",
                    severity=RiskSeverity.HIGH,
                    summary=(
                        f"Debt-to-Equity {debt_to_equity} exceeds the cited maximum "
                        f"{policy_thresholds.maximum_debt_to_equity}."
                    ),
                    policy_citations=citations,
                )
            )

    manual_review_codes = {
        "DSCR_DENOMINATOR_INVALID",
        "CURRENT_RATIO_DENOMINATOR_INVALID",
        "LEVERAGE_DENOMINATOR_INVALID",
        "CREDIT_POLICY_THRESHOLD_UNAVAILABLE",
    }
    status = (
        AssessmentStatus.MANUAL_REVIEW
        if any(flag.code in manual_review_codes for flag in risk_flags)
        else AssessmentStatus.SUCCESS
    )
    return CreditAssessment(
        status=status,
        financial_inputs=financial_inputs,
        calculated_ratios=calculated_ratios,
        policy_thresholds=policy_thresholds,
        risk_flags=risk_flags,
        policy_citations=citations,
        document_evidence=list(document_evidence),
        acknowledged_cross_domain_risks=list(acknowledged_cross_domain_risks),
        rationale_summary=(
            "Ratios were calculated deterministically from the supplied financial inputs; "
            "policy comparisons use only the attached citations."
        ),
    )


__all__ = [
    "CreditAssessment",
    "CreditFinancialInputs",
    "CreditPolicyThresholds",
    "CreditRatios",
    "RatioCalculationError",
    "assess_credit",
    "calculate_current_ratio",
    "calculate_debt_to_equity",
    "calculate_dscr",
]
