"""Typed Human Review Gate for verification actions, not loan decisions."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from .state import (
    ActionPermission,
    CaseContext,
    HumanReviewOutcome,
    HumanReviewRecord,
    IncomeVerificationModel,
    WorkflowState,
)


class HumanReviewError(ValueError):
    """Raised when a review violates state, authority or edit contracts."""


class HumanReviewCommand(IncomeVerificationModel):
    outcome: HumanReviewOutcome
    reason: str = Field(min_length=3)
    approved_action_ids: list[str] = Field(default_factory=list)
    edited_eligible_income: Decimal | None = Field(default=None, ge=0)


def apply_human_review(
    context: CaseContext,
    command: HumanReviewCommand,
    *,
    reviewer_id: str,
) -> CaseContext:
    """Apply one authorized review and route to the next deterministic state."""

    if not reviewer_id.strip():
        raise HumanReviewError("Reviewer identity is required.")
    if context.workflow_state is not WorkflowState.HUMAN_REVIEW:
        raise HumanReviewError("Case is not waiting for human review.")
    if context.recommendation is None:
        raise HumanReviewError("Reviewable recommendation is not available.")

    updated = context.model_copy(deep=True)
    available_actions = {action.action_id: action for action in updated.proposed_actions}
    unknown = sorted(set(command.approved_action_ids) - set(available_actions))
    if unknown:
        raise HumanReviewError("Review references unknown action identifiers.")
    prohibited = [
        action_id
        for action_id in command.approved_action_ids
        if available_actions[action_id].permission is ActionPermission.PROHIBITED
    ]
    if prohibited:
        raise HumanReviewError("Prohibited actions cannot be approved.")

    edited_values = {}
    if command.outcome is HumanReviewOutcome.ACCEPT_ACTIONS:
        if command.edited_eligible_income is not None:
            raise HumanReviewError("Edits require the EDIT_AND_RERUN outcome.")
    elif command.outcome is HumanReviewOutcome.EDIT_AND_RERUN:
        if command.edited_eligible_income is None:
            raise HumanReviewError("EDIT_AND_RERUN requires an explicit edited value.")
        if updated.policy_result is None:
            raise HumanReviewError("Policy result is unavailable for correction.")
        updated.policy_result.eligible_income = command.edited_eligible_income
        edited_values["eligible_income"] = str(command.edited_eligible_income)
    elif command.approved_action_ids:
        raise HumanReviewError("Manual handling cannot approve execution actions.")

    updated.human_review = HumanReviewRecord(
        reviewer_id=reviewer_id,
        outcome=command.outcome,
        reason=command.reason,
        approved_action_ids=command.approved_action_ids,
        edited_values=edited_values,
    )
    updated.add_event(
        "HUMAN_REVIEW_RECORDED",
        actor_type="UNDERWRITER",
        actor_id=reviewer_id,
        details={
            "outcome": command.outcome.value,
            "approved_action_count": len(command.approved_action_ids),
            "has_edits": bool(edited_values),
        },
    )
    if command.outcome is HumanReviewOutcome.ACCEPT_ACTIONS:
        updated.transition_to(
            WorkflowState.EXECUTING_APPROVED_ACTIONS,
            event_type="VERIFICATION_ACTIONS_ACCEPTED",
        )
    elif command.outcome is HumanReviewOutcome.EDIT_AND_RERUN:
        updated.transition_to(
            WorkflowState.BUILDING_RECOMMENDATION,
            event_type="VERIFICATION_RESULT_EDITED",
        )
    else:
        updated.transition_to(
            WorkflowState.MANUAL_REVIEW_REQUIRED,
            event_type="AI_RESULT_NOT_ACCEPTED",
        )
    return updated
