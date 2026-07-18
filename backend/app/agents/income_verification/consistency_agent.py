"""Consistency agent backed exclusively by deterministic rules."""

from __future__ import annotations

from app.tools.consistency_rules import ConsistencyRuleConfig, evaluate_consistency

from .state import CaseContext, ComponentStatus


class ConsistencyInputError(ValueError):
    """Raised when cross-checking starts before required branch results exist."""


def run_consistency_agent(
    context: CaseContext,
    *,
    config: ConsistencyRuleConfig | None = None,
) -> CaseContext:
    """Cross-check extraction, income and policy outputs and update a copied state."""

    updated = context.model_copy(deep=True)
    if updated.extracted_fields is None:
        raise ConsistencyInputError("Extracted fields are required")
    if updated.income_analysis is None or updated.income_analysis.status is not ComponentStatus.SUCCESS:
        raise ConsistencyInputError("Successful income analysis is required")
    if updated.policy_result is None or updated.policy_result.status is not ComponentStatus.SUCCESS:
        raise ConsistencyInputError("Successful policy result is required")

    updated.findings = evaluate_consistency(
        case_id=updated.case_id,
        extracted=updated.extracted_fields,
        income=updated.income_analysis,
        policy=updated.policy_result,
        valid_evidence_ids={item.evidence_id for item in updated.evidence},
        config=config,
    )
    updated.add_event(
        "CONSISTENCY_CHECK_COMPLETED",
        actor_type="CONSISTENCY_AGENT",
        details={"finding_count": len(updated.findings)},
    )
    return updated
