"""Typed deterministic helpers for the Risk Management specialist."""

from collections.abc import Sequence
from decimal import Decimal

from app.schemas.enums import AssessmentStatus, RiskSeverity, RiskTier
from app.schemas.evidence import (
    AgentCitation,
    CaseDocumentEvidence,
    MissingDataRequest,
    PolicyNumericEvidence,
    RiskFlag,
)
from app.schemas.tier2 import (
    ConcentrationLimitCheck,
    RiskManagementAssessment,
)


def calculate_concentration_limit_check(
    current_exposure: Decimal,
    proposed_exposure: Decimal,
    policy_limit: Decimal,
) -> ConcentrationLimitCheck:
    """Compare aggregate exposure with a positive cited policy limit."""

    if current_exposure < 0 or proposed_exposure < 0:
        raise ValueError("Exposure amounts cannot be negative")
    if policy_limit <= 0:
        raise ValueError("Policy concentration limit must be greater than zero")
    return ConcentrationLimitCheck(
        current_exposure=current_exposure,
        proposed_exposure=proposed_exposure,
        policy_limit=policy_limit,
        within_limit=(current_exposure + proposed_exposure) <= policy_limit,
    )


def assess_risk_management(
    risk_tier: RiskTier | None,
    concentration_limit_check: ConcentrationLimitCheck | None,
    industry_risk_summary: str,
    *,
    concentration_policy_evidence: Sequence[PolicyNumericEvidence] = (),
    policy_citations: Sequence[AgentCitation] = (),
    document_evidence: Sequence[CaseDocumentEvidence] = (),
) -> RiskManagementAssessment:
    """Build a risk assessment while failing closed on missing inputs or policy."""

    if not concentration_policy_evidence:
        concentration_limit_check = None

    missing_fields: list[str] = []
    if risk_tier is None or risk_tier == RiskTier.UNASSIGNED:
        missing_fields.append("risk_tier")
    if concentration_limit_check is None:
        missing_fields.extend(
            ["current_exposure", "proposed_exposure", "policy_limit"]
        )
    if not industry_risk_summary.strip():
        missing_fields.append("industry_risk_summary")
    if missing_fields:
        return RiskManagementAssessment(
            status=AssessmentStatus.REQUIRES_MORE_DATA,
            risk_tier=risk_tier or RiskTier.UNASSIGNED,
            concentration_limit_check=concentration_limit_check,
            concentration_policy_evidence=list(concentration_policy_evidence),
            industry_risk_summary=industry_risk_summary,
            missing_data=[
                MissingDataRequest(
                    code="RISK_INPUTS_MISSING",
                    description=(
                        "Exposure, industry, or borrower risk data required for risk "
                        "management assessment is incomplete."
                    ),
                    requested_document_types=[
                        "EXPOSURE_REPORT",
                        "INDUSTRY_RISK_ASSESSMENT",
                    ],
                    requested_fields=missing_fields,
                )
            ],
            document_evidence=list(document_evidence),
            rationale_summary="Risk tier was not inferred from incomplete inputs.",
        )

    citations = list(policy_citations)
    risk_flags: list[RiskFlag] = []
    assert risk_tier is not None
    assert concentration_limit_check is not None
    assert concentration_policy_evidence
    if not citations:
        risk_flags.append(
            RiskFlag(
                code="RISK_POLICY_UNAVAILABLE",
                severity=RiskSeverity.HIGH,
                summary="No approved policy citation supports the risk conclusion.",
                requires_policy_citation=False,
            )
        )
    else:
        if not concentration_limit_check.within_limit:
            risk_flags.append(
                RiskFlag(
                    code="CONCENTRATION_LIMIT_EXCEEDED",
                    severity=RiskSeverity.HIGH,
                    summary=(
                        "Current plus proposed exposure exceeds the cited "
                        "concentration limit."
                    ),
                    policy_citations=citations,
                )
            )
        if risk_tier == RiskTier.HIGH:
            risk_flags.append(
                RiskFlag(
                    code="PRELIMINARY_RISK_TIER_HIGH",
                    severity=RiskSeverity.HIGH,
                    summary="The borrower received a high preliminary risk tier.",
                    policy_citations=citations,
                )
            )

    return RiskManagementAssessment(
        status=(
            AssessmentStatus.SUCCESS
            if citations
            else AssessmentStatus.MANUAL_REVIEW
        ),
        risk_tier=risk_tier,
        concentration_limit_check=concentration_limit_check,
        concentration_policy_evidence=list(concentration_policy_evidence),
        industry_risk_summary=industry_risk_summary,
        risk_flags=risk_flags,
        policy_citations=citations,
        document_evidence=list(document_evidence),
        rationale_summary=(
            "Aggregate exposure was compared deterministically with the cited policy limit."
        ),
    )


__all__ = [
    "ConcentrationLimitCheck",
    "RiskManagementAssessment",
    "assess_risk_management",
    "calculate_concentration_limit_check",
]
