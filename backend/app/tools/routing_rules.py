"""Deterministic routing decisions for consistency findings."""

from __future__ import annotations

from enum import StrEnum

from app.agents.income_verification.state import Finding, FindingSeverity


class ConsistencyRoute(StrEnum):
    BUILD_RECOMMENDATION = "BUILD_RECOMMENDATION"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


SEVERITY_SCORE: dict[FindingSeverity, int] = {
    FindingSeverity.INFO: 0,
    FindingSeverity.WARNING: 1,
    FindingSeverity.CRITICAL: 2,
}


def select_consistency_route(findings: list[Finding]) -> ConsistencyRoute:
    """Route critical inconsistencies to a specialist, without inferring a decision."""

    highest_score = max(
        (SEVERITY_SCORE[finding.severity] for finding in findings),
        default=SEVERITY_SCORE[FindingSeverity.INFO],
    )
    if highest_score >= SEVERITY_SCORE[FindingSeverity.CRITICAL]:
        return ConsistencyRoute.MANUAL_REVIEW_REQUIRED
    return ConsistencyRoute.BUILD_RECOMMENDATION
