"""Single authorized Legal & Compliance specialist assessment builder."""

from collections.abc import Sequence

from app.schemas.enums import AmlRiskLevel, AssessmentStatus, KycStatus, RiskSeverity
from app.schemas.evidence import (
    AgentCitation,
    CaseDocumentEvidence,
    MissingDataRequest,
    RiskFlag,
)
from app.schemas.tier2 import (
    ComplianceFindings,
    LegalComplianceAssessment,
    LegalFindings,
)


def _find_missing_legal_data(
    legal_findings: LegalFindings | None,
) -> list[str]:
    if legal_findings is None:
        return [
            "corporate_governance_valid",
            "title_ownership_verified",
            "unresolved_litigation",
        ]
    missing_fields: list[str] = []
    if legal_findings.corporate_governance_valid is None:
        missing_fields.append("corporate_governance_valid")
    if legal_findings.title_ownership_verified is None:
        missing_fields.append("title_ownership_verified")
    if legal_findings.unresolved_litigation is None:
        missing_fields.append("unresolved_litigation")
    return missing_fields


def _find_missing_compliance_data(
    compliance_findings: ComplianceFindings | None,
) -> list[str]:
    if compliance_findings is None:
        return [
            "kyc_status",
            "aml_risk_level",
            "sanctions_check_passed",
            "regulatory_inquiry_open",
        ]
    missing_fields: list[str] = []
    if compliance_findings.kyc_status == KycStatus.UNKNOWN:
        missing_fields.append("kyc_status")
    if compliance_findings.aml_risk_level == AmlRiskLevel.UNKNOWN:
        missing_fields.append("aml_risk_level")
    if compliance_findings.sanctions_check_passed is None:
        missing_fields.append("sanctions_check_passed")
    if compliance_findings.regulatory_inquiry_open is None:
        missing_fields.append("regulatory_inquiry_open")
    return missing_fields


def assess_legal_compliance(
    legal_findings: LegalFindings | None,
    compliance_findings: ComplianceFindings | None,
    *,
    policy_citations: Sequence[AgentCitation] = (),
    document_evidence: Sequence[CaseDocumentEvidence] = (),
) -> LegalComplianceAssessment:
    """Combine internal legal/compliance results under one Shared Board identity."""

    missing_data: list[MissingDataRequest] = []
    missing_legal = _find_missing_legal_data(legal_findings)
    if missing_legal:
        missing_data.append(
            MissingDataRequest(
                code="LEGAL_DOCUMENTS_INCOMPLETE",
                description=(
                    "Corporate governance, ownership, and litigation evidence is incomplete."
                ),
                requested_document_types=[
                    "CORPORATE_GOVERNANCE_DOCUMENTS",
                    "COLLATERAL_TITLE_DOCUMENTS",
                    "LITIGATION_DECLARATION",
                ],
                requested_fields=missing_legal,
            )
        )
    missing_compliance = _find_missing_compliance_data(compliance_findings)
    if missing_compliance:
        missing_data.append(
            MissingDataRequest(
                code="COMPLIANCE_CHECKS_INCOMPLETE",
                description="Required KYC, AML, sanctions, or regulatory checks are incomplete.",
                requested_document_types=["KYC_PACKAGE", "BENEFICIAL_OWNER_REGISTER"],
                requested_fields=missing_compliance,
            )
        )
    if missing_data:
        return LegalComplianceAssessment(
            status=AssessmentStatus.REQUIRES_MORE_DATA,
            legal=legal_findings,
            compliance=compliance_findings,
            missing_data=missing_data,
            policy_citations=list(policy_citations),
            document_evidence=list(document_evidence),
            rationale_summary=(
                "Legal and compliance analysis stopped because required evidence is incomplete."
            ),
        )

    assert legal_findings is not None
    assert compliance_findings is not None
    risk_flags: list[RiskFlag] = []
    if not legal_findings.corporate_governance_valid:
        risk_flags.append(
            RiskFlag(
                code="CORPORATE_GOVERNANCE_INVALID",
                severity=RiskSeverity.HIGH,
                summary="Corporate governance documents did not pass validation.",
                requires_policy_citation=False,
            )
        )
    if not legal_findings.title_ownership_verified:
        risk_flags.append(
            RiskFlag(
                code="TITLE_OWNERSHIP_UNVERIFIED",
                severity=RiskSeverity.HIGH,
                summary="Collateral title ownership was not verified.",
                requires_policy_citation=False,
            )
        )
    if legal_findings.unresolved_litigation:
        risk_flags.append(
            RiskFlag(
                code="UNRESOLVED_LITIGATION",
                severity=RiskSeverity.HIGH,
                summary=(
                    legal_findings.litigation_risk_summary
                    or "The borrower has unresolved litigation."
                ),
                requires_policy_citation=False,
            )
        )
    if compliance_findings.kyc_status != KycStatus.VERIFIED:
        risk_flags.append(
            RiskFlag(
                code="KYC_NOT_VERIFIED",
                severity=RiskSeverity.CRITICAL,
                summary=f"KYC status is {compliance_findings.kyc_status}.",
                requires_policy_citation=False,
            )
        )
    if compliance_findings.aml_risk_level == AmlRiskLevel.HIGH:
        risk_flags.append(
            RiskFlag(
                code="AML_RISK_HIGH",
                severity=RiskSeverity.CRITICAL,
                summary="AML screening returned a high-risk classification.",
                requires_policy_citation=False,
            )
        )
    if not compliance_findings.sanctions_check_passed:
        risk_flags.append(
            RiskFlag(
                code="SANCTIONS_CHECK_FAILED",
                severity=RiskSeverity.CRITICAL,
                summary="Sanctions screening did not pass.",
                requires_policy_citation=False,
            )
        )
    if compliance_findings.regulatory_inquiry_open:
        risk_flags.append(
            RiskFlag(
                code="REGULATORY_INQUIRY_OPEN",
                severity=RiskSeverity.HIGH,
                summary="An open regulatory inquiry requires human review.",
                requires_policy_citation=False,
            )
        )

    citations = list(policy_citations)
    if not citations:
        risk_flags.append(
            RiskFlag(
                code="LEGAL_COMPLIANCE_POLICY_UNAVAILABLE",
                severity=RiskSeverity.HIGH,
                summary=(
                    "Findings are available, but no approved policy citation was supplied "
                    "for a compliance conclusion."
                ),
                requires_policy_citation=False,
            )
        )
    status = (
        AssessmentStatus.SUCCESS
        if citations
        else AssessmentStatus.MANUAL_REVIEW
    )
    return LegalComplianceAssessment(
        status=status,
        legal=legal_findings,
        compliance=compliance_findings,
        risk_flags=risk_flags,
        policy_citations=citations,
        document_evidence=list(document_evidence),
        rationale_summary=(
            "Legal document review and KYC/AML/sanctions checks were combined under "
            "the single LegalCompliance agent identity."
        ),
    )


__all__ = ["LegalComplianceAssessment", "assess_legal_compliance"]
