"""Internal compliance-analysis module for the LegalCompliance agent identity."""

from app.schemas.enums import AmlRiskLevel, KycStatus
from app.schemas.tier2 import ComplianceFindings


def build_compliance_findings(
    *,
    kyc_status: KycStatus,
    aml_risk_level: AmlRiskLevel,
    sanctions_check_passed: bool | None,
    regulatory_inquiry_open: bool | None,
) -> ComplianceFindings:
    """Return compliance findings only; this module is not an independent agent."""

    return ComplianceFindings(
        kyc_status=kyc_status,
        aml_risk_level=aml_risk_level,
        sanctions_check_passed=sanctions_check_passed,
        regulatory_inquiry_open=regulatory_inquiry_open,
    )


__all__ = ["ComplianceFindings", "build_compliance_findings"]
