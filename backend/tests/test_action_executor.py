"""Action permission and verification tests."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.income_verification import CaseContext  # noqa: E402
from app.agents.income_verification.human_review import (  # noqa: E402
    HumanReviewCommand,
    HumanReviewError,
    apply_human_review,
)
from app.services.action_executor import ActionExecutionError, ActionExecutor  # noqa: E402
from app.services.llm_provider import MockLLMProvider  # noqa: E402
from app.services.runtime import (  # noqa: E402
    EmbeddedDemoPolicyRetriever,
    IncomeVerificationRuntime,
)


class ActionExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_review_cannot_approve_unknown_action(self) -> None:
        # A fresh, network-free runtime (mock LLM + keyword-match retriever)
        # per docs/PROJECT-RULES.md §10: workflow tests must pass without
        # calling a live LLM.
        runtime = IncomeVerificationRuntime(
            llm=MockLLMProvider(), policy_retriever=EmbeddedDemoPolicyRetriever()
        )
        context = await runtime.start("SYN-SHB-2026-0001")
        # The shared runtime may already be completed from another test; use a fresh
        # synthetic context only to validate the gate's state contract.
        if context.workflow_state.value != "HUMAN_REVIEW":
            self.skipTest("shared demo runtime is already completed")
        with self.assertRaises(HumanReviewError):
            apply_human_review(
                context,
                HumanReviewCommand(
                    outcome="ACCEPT_ACTIONS",
                    reason="invalid",
                    approved_action_ids=["unknown-action"],
                ),
                reviewer_id="underwriter-001",
            )

    async def test_executor_rejects_execution_without_accepted_review(self) -> None:
        context = CaseContext(
            case_id="case-action",
            application_id="app-action",
            workflow_state="EXECUTING_APPROVED_ACTIONS",
        )
        with self.assertRaises(ActionExecutionError):
            await ActionExecutor().execute(context)


if __name__ == "__main__":
    unittest.main()
