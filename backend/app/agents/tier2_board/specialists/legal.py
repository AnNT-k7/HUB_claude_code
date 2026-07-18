"""Internal legal-analysis module for the LegalCompliance specialist identity."""

from app.schemas.tier2 import LegalFindings


def build_legal_findings(
    *,
    corporate_governance_valid: bool | None,
    title_ownership_verified: bool | None,
    unresolved_litigation: bool | None,
    litigation_risk_summary: str = "",
) -> LegalFindings:
    """Return legal findings only; this module is not an independent agent."""

    return LegalFindings(
        corporate_governance_valid=corporate_governance_valid,
        title_ownership_verified=title_ownership_verified,
        unresolved_litigation=unresolved_litigation,
        litigation_risk_summary=litigation_risk_summary,
    )


__all__ = ["LegalFindings", "build_legal_findings"]
