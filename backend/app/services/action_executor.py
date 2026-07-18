"""Rule-based execution of typed, human-gated income-verification actions."""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.income_verification.state import (
    ActionPermission,
    ActionType,
    CaseContext,
    ExecutionResult,
    ExecutionStatus,
    HumanReviewOutcome,
    WorkflowState,
)
from app.services.integrations.mvp import ActionGateway, InMemoryActionGateway


class ActionExecutionError(ValueError):
    """Raised when actions cannot be executed safely."""


@dataclass(frozen=True, slots=True)
class ActionExecutorConfig:
    permission_matrix: tuple[tuple[ActionType, ActionPermission], ...] = (
        (ActionType.UPDATE_INCOME_DRAFT, ActionPermission.AUTO_REVERSIBLE),
        (ActionType.ATTACH_EVIDENCE, ActionPermission.AUTO_REVERSIBLE),
        (ActionType.CREATE_EXCEPTION_TASK, ActionPermission.AUTO_REVERSIBLE),
        (ActionType.REQUEST_DOCUMENTS, ActionPermission.HUMAN_REQUIRED),
    )


class ActionExecutor:
    """Validate, execute, verify and audit every selected action."""

    def __init__(
        self,
        gateway: ActionGateway | None = None,
        *,
        config: ActionExecutorConfig | None = None,
    ) -> None:
        self.gateway = gateway or InMemoryActionGateway()
        self.config = config or ActionExecutorConfig()
        self._permissions = dict(self.config.permission_matrix)

    async def execute(self, context: CaseContext) -> CaseContext:
        if context.workflow_state not in {
            WorkflowState.EXECUTING_APPROVED_ACTIONS,
            WorkflowState.TECHNICAL_ERROR,
        }:
            raise ActionExecutionError("Case is not in an executable workflow state.")
        review = context.human_review
        if review is None or review.outcome is not HumanReviewOutcome.ACCEPT_ACTIONS:
            raise ActionExecutionError("Accepted human review is required before execution.")

        updated = context.model_copy(deep=True)
        if updated.workflow_state is WorkflowState.TECHNICAL_ERROR:
            updated.transition_to(
                WorkflowState.EXECUTING_APPROVED_ACTIONS,
                event_type="ACTION_RETRY_STARTED",
            )
        approved_ids = set(review.approved_action_ids)
        results: list[ExecutionResult] = []
        failed = False
        for action in updated.proposed_actions:
            expected_permission = self._permissions.get(action.action_type)
            if expected_permission is None or action.permission is not expected_permission:
                raise ActionExecutionError("Action permission does not match the permission matrix.")
            idempotency_key = f"{updated.case_id}:{action.action_id}"
            if action.permission is ActionPermission.HUMAN_REQUIRED and (
                action.action_id not in approved_ids
            ):
                results.append(
                    ExecutionResult(
                        action_id=action.action_id,
                        status=ExecutionStatus.SKIPPED,
                        idempotency_key=idempotency_key,
                        verified=True,
                        reason_code="NOT_SELECTED_BY_REVIEWER",
                    )
                )
                continue
            try:
                gateway_result = await self.gateway.execute(
                    action_type=action.action_type,
                    application_id=updated.application_id,
                    parameters=action.parameters,
                    idempotency_key=idempotency_key,
                )
                verified = await self.gateway.verify(gateway_result.result_reference)
            except Exception:
                verified = False
                gateway_result = None
            if gateway_result is None or not verified:
                failed = True
                result = ExecutionResult(
                    action_id=action.action_id,
                    status=ExecutionStatus.FAILED,
                    idempotency_key=idempotency_key,
                    verified=False,
                    reason_code="MOCK_GATEWAY_EXECUTION_NOT_VERIFIED",
                )
            else:
                result = ExecutionResult(
                    action_id=action.action_id,
                    status=(
                        ExecutionStatus.DUPLICATE
                        if gateway_result.duplicate
                        else ExecutionStatus.SUCCESS
                    ),
                    idempotency_key=idempotency_key,
                    result_reference=gateway_result.result_reference,
                    verified=True,
                )
            results.append(result)
            updated.add_event(
                "ACTION_EXECUTION_RECORDED",
                actor_type="ACTION_EXECUTOR",
                details={
                    "action_id": action.action_id,
                    "action_type": action.action_type.value,
                    "status": result.status.value,
                    "verified": result.verified,
                },
            )

        updated.execution_results.extend(results)
        if failed:
            updated.transition_to(
                WorkflowState.TECHNICAL_ERROR,
                event_type="ACTION_EXECUTION_FAILED",
            )
            return updated
        updated.transition_to(
            WorkflowState.VERIFYING_EXECUTION,
            event_type="ACTIONS_EXECUTED",
        )
        if not all(result.verified for result in results):
            raise ActionExecutionError("Execution verification is incomplete.")
        updated.transition_to(
            WorkflowState.COMPLETED,
            event_type="EXECUTION_VERIFIED",
        )
        if updated.recommendation is not None:
            from app.agents.income_verification.state import VerificationResultStatus

            updated.recommendation.status = VerificationResultStatus.COMPLETED
        return updated
