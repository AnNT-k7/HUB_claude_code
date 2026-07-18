"""Asynchronous, checkpointed orchestration for income verification Phase 3."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, TypedDict, TypeVar

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.tools.consistency_rules import ConsistencyRuleConfig
from app.tools.routing_rules import ConsistencyRoute, select_consistency_route

from .consistency_agent import ConsistencyInputError, run_consistency_agent
from .recommendation_builder import RecommendationInputError, build_recommendation
from .state import (
    CaseContext,
    ComponentStatus,
    DocumentExtractionResult,
    DocumentRecord,
    DocumentStatus,
    IncomeAnalysisResult,
    PolicyResult,
    WorkflowError,
    WorkflowState,
)
from app.db.models import VerificationCheckpoint


FetchDocuments = Callable[[CaseContext], Awaitable[list[DocumentRecord]]]
ExtractDocuments = Callable[[CaseContext], Awaitable[DocumentExtractionResult]]
AnalyzeIncome = Callable[[CaseContext], Awaitable[IncomeAnalysisResult]]
RetrievePolicy = Callable[[CaseContext], Awaitable[PolicyResult]]


@dataclass(frozen=True, slots=True)
class WorkflowDependencies:
    """Ports implemented by document, income and policy components from earlier phases."""

    fetch_documents: FetchDocuments
    extract_documents: ExtractDocuments
    analyze_income: AnalyzeIncome
    retrieve_policy: RetrievePolicy


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    max_attempts: int = 2
    component_timeout_seconds: float = 30.0
    retry_backoff_seconds: float = 0.05
    consistency_rules: ConsistencyRuleConfig = ConsistencyRuleConfig()

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.component_timeout_seconds <= 0:
            raise ValueError("component_timeout_seconds must be positive")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds cannot be negative")


class ConcurrentStateError(RuntimeError):
    """Raised when another workflow run has already advanced the same case."""


class CheckpointStore(Protocol):
    async def load(self, case_id: str) -> CaseContext | None: ...

    async def save(self, context: CaseContext, *, expected_version: int) -> None: ...


class InMemoryCheckpointStore:
    """Test/development checkpoint store with optimistic concurrency control."""

    def __init__(self) -> None:
        self._states: dict[str, CaseContext] = {}
        self._lock = asyncio.Lock()

    async def load(self, case_id: str) -> CaseContext | None:
        async with self._lock:
            state = self._states.get(case_id)
            return state.model_copy(deep=True) if state is not None else None

    async def save(self, context: CaseContext, *, expected_version: int) -> None:
        async with self._lock:
            existing = self._states.get(context.case_id)
            current_version = existing.state_version if existing is not None else 0
            if current_version != expected_version:
                raise ConcurrentStateError(
                    f"Case {context.case_id} checkpoint version changed"
                )
            self._states[context.case_id] = context.model_copy(deep=True)


class SqlAlchemyCheckpointStore:
    """Optimistic-locking checkpoint store for PostgreSQL-backed deployments."""

    def __init__(self, session_factory: Callable[[], object]) -> None:
        self.session_factory = session_factory

    async def load(self, case_id: str) -> CaseContext | None:
        return await asyncio.to_thread(self._load_sync, case_id)

    async def save(self, context: CaseContext, *, expected_version: int) -> None:
        await asyncio.to_thread(self._save_sync, context, expected_version)

    def _load_sync(self, case_id: str) -> CaseContext | None:
        with self.session_factory() as session:
            row = session.execute(
                select(VerificationCheckpoint).where(
                    VerificationCheckpoint.case_id == case_id
                )
            ).scalar_one_or_none()
            return CaseContext.model_validate(row.context_payload) if row else None

    def _save_sync(self, context: CaseContext, expected_version: int) -> None:
        with self.session_factory() as session:
            row = session.get(VerificationCheckpoint, context.case_id)
            current_version = row.state_version if row is not None else 0
            if current_version != expected_version:
                raise ConcurrentStateError(
                    f"Case {context.case_id} checkpoint version changed"
                )
            payload = context.model_dump(mode="json")
            if row is None:
                row = VerificationCheckpoint(
                    case_id=context.case_id,
                    application_id=context.application_id,
                    state_version=context.state_version,
                    workflow_state=context.workflow_state.value,
                    context_payload=payload,
                )
                session.add(row)
            else:
                row.application_id = context.application_id
                row.state_version = context.state_version
                row.workflow_state = context.workflow_state.value
                row.context_payload = payload
            session.commit()


class _GraphState(TypedDict):
    context: CaseContext


ResultT = TypeVar("ResultT")


class IncomeVerificationOrchestrator:
    """Run Phase 3 and stop before any approved action is executed."""

    TERMINAL_STATES = {
        WorkflowState.HUMAN_REVIEW,
        WorkflowState.AWAITING_DOCUMENTS,
        WorkflowState.MANUAL_REVIEW_REQUIRED,
        WorkflowState.EXECUTING_APPROVED_ACTIONS,
        WorkflowState.VERIFYING_EXECUTION,
        WorkflowState.TECHNICAL_ERROR,
        WorkflowState.COMPLETED,
    }

    def __init__(
        self,
        dependencies: WorkflowDependencies,
        *,
        checkpoint_store: CheckpointStore | None = None,
        config: WorkflowConfig | None = None,
    ) -> None:
        self.dependencies = dependencies
        self.checkpoint_store = checkpoint_store or InMemoryCheckpointStore()
        self.config = config or WorkflowConfig()
        self._graph = self._build_graph()

    async def run(self, context: CaseContext) -> CaseContext:
        """Start or resume a case from its latest persisted checkpoint."""

        persisted = await self.checkpoint_store.load(context.case_id)
        starting_context = persisted or context.model_copy(deep=True)
        if persisted is not None and persisted.application_id != context.application_id:
            raise ValueError("case_id is already associated with another application")
        if starting_context.workflow_state in self.TERMINAL_STATES:
            return starting_context

        result = await self._graph.ainvoke(
            {"context": starting_context},
            config={"recursion_limit": 50},
        )
        return result["context"]

    def _build_graph(self):
        builder = StateGraph(_GraphState)
        builder.add_node("route", self._route_node)
        builder.add_node("open_case", self._open_case)
        builder.add_node("fetch_documents", self._fetch_documents)
        builder.add_node("extract_documents", self._extract_documents)
        builder.add_node("analyze_income_and_policy", self._analyze_income_and_policy)
        builder.add_node("cross_check", self._cross_check)
        builder.add_node("build_recommendation", self._build_recommendation)
        builder.add_edge(START, "route")
        builder.add_conditional_edges(
            "route",
            self._route,
            {
                "open_case": "open_case",
                "fetch_documents": "fetch_documents",
                "extract_documents": "extract_documents",
                "analyze_income_and_policy": "analyze_income_and_policy",
                "cross_check": "cross_check",
                "build_recommendation": "build_recommendation",
                "end": END,
            },
        )
        for node in (
            "open_case",
            "fetch_documents",
            "extract_documents",
            "analyze_income_and_policy",
            "cross_check",
            "build_recommendation",
        ):
            builder.add_edge(node, "route")
        return builder.compile()

    async def _route_node(self, state: _GraphState) -> _GraphState:
        return state

    def _route(self, state: _GraphState) -> str:
        routes = {
            WorkflowState.OPEN_CASE: "open_case",
            WorkflowState.FETCHING_DOCUMENTS: "fetch_documents",
            WorkflowState.EXTRACTING_DOCUMENT_DATA: "extract_documents",
            WorkflowState.ANALYZING_INCOME_AND_POLICY: "analyze_income_and_policy",
            WorkflowState.CROSS_CHECKING: "cross_check",
            WorkflowState.BUILDING_RECOMMENDATION: "build_recommendation",
        }
        return routes.get(state["context"].workflow_state, "end")

    async def _persist(self, previous: CaseContext, updated: CaseContext) -> _GraphState:
        await self.checkpoint_store.save(
            updated,
            expected_version=previous.state_version,
        )
        return {"context": updated}

    async def _open_case(self, state: _GraphState) -> _GraphState:
        previous = state["context"]
        updated = previous.model_copy(deep=True)
        updated.transition_to(WorkflowState.FETCHING_DOCUMENTS)
        return await self._persist(previous, updated)

    async def _fetch_documents(self, state: _GraphState) -> _GraphState:
        previous = state["context"]
        updated = previous.model_copy(deep=True)
        result, errors, attempts = await self._call_with_retry(
            "document_fetch",
            self.dependencies.fetch_documents,
            updated,
        )
        self._record_component_outcome(updated, "document_fetch", errors, attempts)
        if result is None:
            updated.transition_to(
                WorkflowState.MANUAL_REVIEW_REQUIRED,
                event_type="DOCUMENT_FETCH_FAILED",
            )
        else:
            updated.documents = result
            if not result or any(item.status is DocumentStatus.MISSING for item in result):
                updated.transition_to(
                    WorkflowState.AWAITING_DOCUMENTS,
                    event_type="DOCUMENTS_MISSING",
                )
            elif any(item.status is DocumentStatus.UNREADABLE for item in result):
                updated.transition_to(
                    WorkflowState.MANUAL_REVIEW_REQUIRED,
                    event_type="DOCUMENT_UNREADABLE",
                )
            else:
                updated.transition_to(WorkflowState.EXTRACTING_DOCUMENT_DATA)
        return await self._persist(previous, updated)

    async def _extract_documents(self, state: _GraphState) -> _GraphState:
        previous = state["context"]
        updated = previous.model_copy(deep=True)
        result, errors, attempts = await self._call_with_retry(
            "document_extraction",
            self.dependencies.extract_documents,
            updated,
        )
        self._record_component_outcome(updated, "document_extraction", errors, attempts)
        if result is None:
            updated.transition_to(
                WorkflowState.MANUAL_REVIEW_REQUIRED,
                event_type="DOCUMENT_EXTRACTION_FAILED",
            )
        elif result.status is ComponentStatus.MISSING_DATA:
            updated.evidence = result.evidence
            updated.transition_to(
                WorkflowState.AWAITING_DOCUMENTS,
                event_type="EXTRACTED_DATA_INCOMPLETE",
            )
        elif result.status is not ComponentStatus.SUCCESS or result.extracted_fields is None:
            updated.transition_to(
                WorkflowState.MANUAL_REVIEW_REQUIRED,
                event_type="DOCUMENT_EXTRACTION_REQUIRES_REVIEW",
            )
        else:
            updated.extracted_fields = result.extracted_fields
            updated.evidence = result.evidence
            updated.transition_to(WorkflowState.ANALYZING_INCOME_AND_POLICY)
        return await self._persist(previous, updated)

    async def _analyze_income_and_policy(self, state: _GraphState) -> _GraphState:
        previous = state["context"]
        updated = previous.model_copy(deep=True)
        income_task = self._call_with_retry(
            "income_analysis", self.dependencies.analyze_income, updated.model_copy(deep=True)
        )
        policy_task = self._call_with_retry(
            "policy_retrieval", self.dependencies.retrieve_policy, updated.model_copy(deep=True)
        )
        income_outcome, policy_outcome = await asyncio.gather(income_task, policy_task)
        income_result, income_errors, income_attempts = income_outcome
        policy_result, policy_errors, policy_attempts = policy_outcome
        self._record_component_outcome(
            updated, "income_analysis", income_errors, income_attempts
        )
        self._record_component_outcome(
            updated, "policy_retrieval", policy_errors, policy_attempts
        )
        updated.income_analysis = income_result
        updated.policy_result = policy_result

        if (
            income_result is None
            or policy_result is None
            or income_result.status is not ComponentStatus.SUCCESS
            or policy_result.status is not ComponentStatus.SUCCESS
        ):
            updated.transition_to(
                WorkflowState.MANUAL_REVIEW_REQUIRED,
                event_type="ANALYSIS_BRANCH_REQUIRES_REVIEW",
                details={
                    "income_status": income_result.status.value if income_result else "ERROR",
                    "policy_status": policy_result.status.value if policy_result else "ERROR",
                },
            )
        elif policy_result.eligible_income is None or income_result.average_income is None:
            updated.transition_to(
                WorkflowState.MANUAL_REVIEW_REQUIRED,
                event_type="ANALYSIS_OUTPUT_INCOMPLETE",
            )
        else:
            updated.transition_to(WorkflowState.CROSS_CHECKING)
        return await self._persist(previous, updated)

    async def _cross_check(self, state: _GraphState) -> _GraphState:
        previous = state["context"]
        try:
            updated = run_consistency_agent(
                previous,
                config=self.config.consistency_rules,
            )
        except ConsistencyInputError:
            updated = previous.model_copy(deep=True)
            updated.transition_to(
                WorkflowState.MANUAL_REVIEW_REQUIRED,
                event_type="CONSISTENCY_INPUT_INVALID",
            )
        else:
            route = select_consistency_route(updated.findings)
            if route is ConsistencyRoute.MANUAL_REVIEW_REQUIRED:
                updated.transition_to(
                    WorkflowState.MANUAL_REVIEW_REQUIRED,
                    event_type="MATERIAL_INCONSISTENCY_FOUND",
                    details={"finding_count": len(updated.findings)},
                )
            else:
                updated.transition_to(WorkflowState.BUILDING_RECOMMENDATION)
        return await self._persist(previous, updated)

    async def _build_recommendation(self, state: _GraphState) -> _GraphState:
        previous = state["context"]
        try:
            updated = build_recommendation(previous)
        except RecommendationInputError:
            updated = previous.model_copy(deep=True)
            updated.transition_to(
                WorkflowState.MANUAL_REVIEW_REQUIRED,
                event_type="RECOMMENDATION_INPUT_INVALID",
            )
        else:
            updated.transition_to(WorkflowState.HUMAN_REVIEW)
        return await self._persist(previous, updated)

    async def _call_with_retry(
        self,
        component: str,
        operation: Callable[[CaseContext], Awaitable[ResultT]],
        context: CaseContext,
    ) -> tuple[ResultT | None, list[WorkflowError], int]:
        errors: list[WorkflowError] = []
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = await asyncio.wait_for(
                    operation(context.model_copy(deep=True)),
                    timeout=self.config.component_timeout_seconds,
                )
                return result, errors, attempt
            except Exception as exc:
                retryable = attempt < self.config.max_attempts
                errors.append(
                    WorkflowError(
                        code="COMPONENT_TIMEOUT" if isinstance(exc, TimeoutError) else "COMPONENT_FAILURE",
                        component=component,
                        message=f"{component} did not complete successfully",
                        retryable=retryable,
                        attempt=attempt,
                    )
                )
                if not retryable:
                    return None, errors, attempt
                await asyncio.sleep(self.config.retry_backoff_seconds * attempt)
        raise AssertionError("retry loop must return")

    @staticmethod
    def _record_component_outcome(
        context: CaseContext,
        component: str,
        errors: list[WorkflowError],
        attempts: int,
    ) -> None:
        context.retry_counts[component] = max(0, attempts - 1)
        for error in errors:
            context.add_error(error)
        context.add_event(
            "COMPONENT_COMPLETED" if not errors or errors[-1].retryable else "COMPONENT_FAILED",
            actor_type="ORCHESTRATOR",
            details={"component": component, "attempts": attempts},
        )
