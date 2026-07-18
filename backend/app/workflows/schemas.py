from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import AgentID, SPECIALIST_AGENT_IDS


# Compatibility name for workflow consumers; the enum itself is the application's
# single canonical Shared Board agent identity.
AgentId = AgentID


class WorkflowStepType(str, Enum):
    ORCHESTRATOR = "orchestrator"
    SPECIALIST = "specialist"
    REVIEWER = "reviewer"
    HUMAN_GATE = "human_gate"
    OPERATIONS = "operations"


class WorkflowStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=100)
    type: WorkflowStepType
    agent: AgentID | None = None
    depends_on: tuple[str, ...] = ()
    description: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_agent_for_step_type(self) -> "WorkflowStep":
        expected_agent = {
            WorkflowStepType.ORCHESTRATOR: AgentID.BANKING_ORCHESTRATOR,
            WorkflowStepType.REVIEWER: AgentID.REVIEWER,
            WorkflowStepType.OPERATIONS: AgentID.BANKING_OPERATIONS,
        }

        if self.type == WorkflowStepType.HUMAN_GATE:
            if self.agent is not None:
                raise ValueError("human_gate steps cannot be assigned to an agent")
            return self

        if self.agent is None:
            raise ValueError(f"{self.type.value} steps require an agent")

        if self.type == WorkflowStepType.SPECIALIST:
            if self.agent not in SPECIALIST_AGENT_IDS:
                raise ValueError(
                    f"{self.agent.value} is not an authorized specialist agent"
                )
            return self

        required = expected_agent[self.type]
        if self.agent != required:
            raise ValueError(
                f"{self.type.value} steps must be assigned to {required.value}"
            )
        return self


class WorkflowOutcomeRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    missing_data_case_status: Literal["AWAITING_DOCS"] = "AWAITING_DOCS"
    consensus_case_status: Literal["TIER3_PENDING_REVIEW"] = (
        "TIER3_PENDING_REVIEW"
    )
    max_rounds_case_status: Literal["TIER3_PENDING_REVIEW"] = (
        "TIER3_PENDING_REVIEW"
    )
    require_human_approval_for_operations: Literal[True] = True


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=100)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+$", max_length=32)
    description: str = Field(min_length=1, max_length=500)
    max_debate_rounds: int = Field(default=3, ge=1, le=10)
    outcomes: WorkflowOutcomeRules = Field(default_factory=WorkflowOutcomeRules)
    steps: tuple[WorkflowStep, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_execution_graph(self) -> "WorkflowDefinition":
        step_by_id = {step.id: step for step in self.steps}
        if len(step_by_id) != len(self.steps):
            raise ValueError("workflow step IDs must be unique")

        for step in self.steps:
            if len(set(step.depends_on)) != len(step.depends_on):
                raise ValueError(f"step {step.id} contains duplicate dependencies")
            if step.id in step.depends_on:
                raise ValueError(f"step {step.id} cannot depend on itself")
            unknown = set(step.depends_on) - step_by_id.keys()
            if unknown:
                names = ", ".join(sorted(unknown))
                raise ValueError(f"step {step.id} has unknown dependencies: {names}")

        self._assert_acyclic(step_by_id)

        human_gates = [
            step for step in self.steps if step.type == WorkflowStepType.HUMAN_GATE
        ]
        operations_steps = [
            step for step in self.steps if step.type == WorkflowStepType.OPERATIONS
        ]
        reviewer_steps = [
            step for step in self.steps if step.type == WorkflowStepType.REVIEWER
        ]
        specialist_steps = [
            step for step in self.steps if step.type == WorkflowStepType.SPECIALIST
        ]

        if len(human_gates) != 1:
            raise ValueError("workflow must contain exactly one human_gate step")
        if len(operations_steps) != 1:
            raise ValueError("workflow must contain exactly one operations step")
        if len(reviewer_steps) != 1:
            raise ValueError("workflow must contain exactly one reviewer step")
        if not specialist_steps:
            raise ValueError("workflow must contain at least one specialist step")

        reviewer = reviewer_steps[0]
        reviewer_ancestors = self._ancestors(reviewer.id, step_by_id)
        missing_from_review = {
            step.id for step in specialist_steps if step.id not in reviewer_ancestors
        }
        if missing_from_review:
            names = ", ".join(sorted(missing_from_review))
            raise ValueError(f"reviewer must follow every specialist step: {names}")

        human_gate = human_gates[0]
        if reviewer.id not in self._ancestors(human_gate.id, step_by_id):
            raise ValueError("human_gate must follow the reviewer step")

        operations_step = operations_steps[0]
        if human_gate.id not in self._ancestors(operations_step.id, step_by_id):
            raise ValueError("operations must transitively depend on human_gate")
        return self

    @staticmethod
    def _assert_acyclic(step_by_id: dict[str, WorkflowStep]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError(f"workflow contains a cycle at step {step_id}")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in step_by_id[step_id].depends_on:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for current_step_id in step_by_id:
            visit(current_step_id)

    @staticmethod
    def _ancestors(
        step_id: str, step_by_id: dict[str, WorkflowStep]
    ) -> set[str]:
        ancestors: set[str] = set()
        pending = list(step_by_id[step_id].depends_on)
        while pending:
            dependency = pending.pop()
            if dependency in ancestors:
                continue
            ancestors.add(dependency)
            pending.extend(step_by_id[dependency].depends_on)
        return ancestors

    def get_step(self, step_id: str) -> WorkflowStep:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise KeyError(f"unknown workflow step: {step_id}")

    def execution_layers(self) -> tuple[tuple[WorkflowStep, ...], ...]:
        """Return deterministic topological layers; steps in a layer may run in parallel."""

        remaining = {step.id: step for step in self.steps}
        completed: set[str] = set()
        layers: list[tuple[WorkflowStep, ...]] = []

        while remaining:
            ready = tuple(
                sorted(
                    (
                        step
                        for step in remaining.values()
                        if set(step.depends_on) <= completed
                    ),
                    key=lambda step: step.id,
                )
            )
            if not ready:
                raise RuntimeError("validated workflow unexpectedly contains a cycle")
            layers.append(ready)
            for step in ready:
                completed.add(step.id)
                del remaining[step.id]
        return tuple(layers)
