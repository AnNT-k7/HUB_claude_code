"""Build a review-ready income verification recommendation."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from .state import (
    ActionPermission,
    ActionType,
    CaseContext,
    FindingSeverity,
    ProposedAction,
    Recommendation,
    VerificationResultStatus,
)


class RecommendationInputError(ValueError):
    """Raised when required analysis data is absent."""


def _action_id(case_id: str, action_type: ActionType) -> str:
    return str(uuid5(NAMESPACE_URL, f"income-verification:{case_id}:action:{action_type.value}"))


def build_recommendation(context: CaseContext) -> CaseContext:
    """Create a recommendation draft; this function never decides the loan."""

    updated = context.model_copy(deep=True)
    if updated.extracted_fields is None:
        raise RecommendationInputError("Extracted fields are required")
    if updated.income_analysis is None or updated.policy_result is None:
        raise RecommendationInputError("Income and policy results are required")

    extracted = updated.extracted_fields
    income = updated.income_analysis
    policy = updated.policy_result
    missing_documents = sorted(
        set(extracted.missing_documents).union(policy.required_documents)
        - {document.document_type for document in updated.documents}
    )
    unresolved = [
        finding.message
        for finding in updated.findings
        if finding.severity in {FindingSeverity.WARNING, FindingSeverity.CRITICAL}
    ]
    status = (
        VerificationResultStatus.NEEDS_CLARIFICATION
        if missing_documents or unresolved
        else VerificationResultStatus.READY_FOR_REVIEW
    )

    updated.recommendation = Recommendation(
        status=status,
        summary=(
            "Income verification analysis is prepared for specialist review. "
            "The recommendation is evidence-based and is not a lending decision."
        ),
        declared_income=extracted.declared_income,
        average_income=income.average_income,
        eligible_income=policy.eligible_income,
        currency=policy.currency or income.currency or extracted.currency,
        findings=updated.findings,
        missing_documents=missing_documents,
        policy_citations=policy.citations,
        unresolved_issues=unresolved,
    )

    evidence_ids = sorted({item.evidence_id for item in updated.evidence})
    actions = [
        ProposedAction(
            action_id=_action_id(updated.case_id, ActionType.UPDATE_INCOME_DRAFT),
            action_type=ActionType.UPDATE_INCOME_DRAFT,
            description="Prepare verified income values as a reversible case draft.",
            parameters={
                "average_income": str(income.average_income) if income.average_income is not None else None,
                "eligible_income": str(policy.eligible_income) if policy.eligible_income is not None else None,
                "currency": policy.currency or income.currency or extracted.currency,
            },
            permission=ActionPermission.AUTO_REVERSIBLE,
            evidence_ids=evidence_ids,
        ),
        ProposedAction(
            action_id=_action_id(updated.case_id, ActionType.ATTACH_EVIDENCE),
            action_type=ActionType.ATTACH_EVIDENCE,
            description="Attach traceable evidence and policy citations to the review draft.",
            parameters={"evidence_count": len(evidence_ids)},
            permission=ActionPermission.AUTO_REVERSIBLE,
            evidence_ids=evidence_ids,
        ),
    ]
    if missing_documents:
        actions.append(
            ProposedAction(
                action_id=_action_id(updated.case_id, ActionType.REQUEST_DOCUMENTS),
                action_type=ActionType.REQUEST_DOCUMENTS,
                description="Request missing supporting documents after specialist approval.",
                parameters={"document_types": ",".join(missing_documents)},
                permission=ActionPermission.HUMAN_REQUIRED,
                evidence_ids=[],
            )
        )
    if unresolved:
        actions.append(
            ProposedAction(
                action_id=_action_id(updated.case_id, ActionType.CREATE_EXCEPTION_TASK),
                action_type=ActionType.CREATE_EXCEPTION_TASK,
                description="Create an internal exception task for unresolved inconsistencies.",
                parameters={"issue_count": len(unresolved)},
                permission=ActionPermission.AUTO_REVERSIBLE,
                evidence_ids=evidence_ids,
            )
        )

    updated.proposed_actions = actions
    updated.add_event(
        "RECOMMENDATION_BUILT",
        actor_type="RECOMMENDATION_BUILDER",
        details={"status": status.value, "action_count": len(actions)},
    )
    return updated
