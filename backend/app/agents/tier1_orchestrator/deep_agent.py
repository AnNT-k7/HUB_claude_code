from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable, Iterable, Sequence
from typing import Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.tier2_board import Reviewer, SharedBoardManager
from app.agents.tier2_board.runtime import SpecialistAgentRuntime
from app.agents.tier1_orchestrator.replanner import replan_for_missing_data
from app.config import get_settings
from app.db.models import AuditOutcome, Case, CaseStatus, Document, DocumentStatus
from app.schemas import (
    AgentCitation,
    AgentID,
    AssessmentStatus,
    DebateIssue,
    DebateRecord,
    MissingDataRequest,
    RiskSeverity,
    SharedBoardState,
    SpecialistAssessment,
    TaskState,
)
from app.schemas.base import ContractModel
from app.services.audit import write_audit_log
from app.services.board_repository import SqlSharedBoardRepository
from app.services.llm import OpenAICompatibleStructuredLLM, StructuredLLM
from app.services.rag import (
    AgentPolicyRetriever,
    EmbeddingProvider,
    create_embedding_provider,
)
from app.workflows import WorkflowDefinition, get_workflow
from app.workflows.schemas import WorkflowStepType


class DeepAgentError(RuntimeError):
    pass


class CaseNotAssessableError(DeepAgentError):
    pass


class OrchestratorState(TypedDict, total=False):
    case_id: str
    review_route: Literal["revise", "synthesize"]
    revision_targets: list[str]


class PlanInterpretation(ContractModel):
    case_summary: str = Field(min_length=1, max_length=2_000)
    focus_areas: list[str] = Field(default_factory=list, max_length=20)
    observed_missing_sections: list[str] = Field(default_factory=list, max_length=20)


class SemanticReviewOutput(ContractModel):
    issues: list[DebateIssue] = Field(default_factory=list, max_length=20)


class AssessmentDraft(ContractModel):
    executive_summary: str = Field(min_length=1, max_length=6_000)
    overall_risk_level: Literal["LOW", "MEDIUM", "HIGH", "MANUAL_REVIEW"]
    key_strengths: list[str] = Field(default_factory=list, max_length=30)
    key_risks: list[str] = Field(default_factory=list, max_length=30)
    officer_attention_items: list[str] = Field(default_factory=list, max_length=30)
    disclaimer: str = Field(min_length=1, max_length=1_000)


LLMFactory = Callable[[], StructuredLLM]


POLICY_QUERIES: dict[AgentID, str] = {
    AgentID.CUSTOMER_RELATIONSHIP: (
        "corporate loan intake required documents borrower profile requested terms"
    ),
    AgentID.CREDIT: (
        "corporate credit DSCR current ratio debt to equity minimum maximum thresholds"
    ),
    AgentID.RISK_MANAGEMENT: (
        "industry risk concentration exposure limit legal contingency risk tier"
    ),
    AgentID.LEGAL_COMPLIANCE: (
        "KYC AML sanctions governance title ownership litigation compliance"
    ),
    AgentID.COLLATERAL_APPRAISAL: (
        "collateral eligible value commercial real estate maximum LTV"
    ),
}


class DeepAgentOrchestrator:
    """One LangGraph supervisor coordinating all specialists via Shared Board."""

    def __init__(
        self,
        db: Session,
        *,
        llm_factory: LLMFactory | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._db = db
        self._llm_factory = llm_factory or OpenAICompatibleStructuredLLM
        self._embedding_provider = embedding_provider
        self._case: Case | None = None
        self._case_payload: dict[str, object] | None = None
        self._workflow: WorkflowDefinition | None = None
        self._repository: SqlSharedBoardRepository | None = None
        self._manager: SharedBoardManager | None = None
        self._policy_citations: dict[AgentID, list[AgentCitation]] = {}
        self._reviewer = Reviewer()
        self._specialist_runtime = SpecialistAgentRuntime(self._llm_factory)

    def run(self, case_id: UUID) -> SharedBoardState:
        case = self._db.get(Case, case_id)
        if case is None:
            raise LookupError(f"Case {case_id} was not found")
        if case.status in {
            CaseStatus.APPROVED.value,
            CaseStatus.REJECTED.value,
            CaseStatus.COMPLETED.value,
        }:
            raise CaseNotAssessableError(
                f"Case in {case.status} status cannot start another assessment"
            )
        self._case = case
        self._case_payload = self._build_case_payload(case)
        settings = get_settings()
        self._workflow = get_workflow(
            case.workflow_id,
            settings.workflow_definition.parent,
            expected_version=case.workflow_version,
        )
        if self._workflow.max_debate_rounds > settings.max_debate_rounds:
            raise CaseNotAssessableError(
                "Workflow debate limit exceeds the configured safety maximum"
            )
        self._repository = SqlSharedBoardRepository(
            self._db,
            workflow_id=self._workflow.workflow_id,
            workflow_version=self._workflow.version,
        )
        self._manager = SharedBoardManager(self._repository)

        existing = self._repository.get_by_case_id(case_id)
        if (
            existing is not None
            and existing.final_summary is not None
            and case.status == CaseStatus.TIER3_PENDING_REVIEW.value
        ):
            return existing

        graph = self._build_graph()
        try:
            graph.invoke(
                {"case_id": str(case_id)},
                {"recursion_limit": self._workflow.max_debate_rounds * 3 + 12},
            )
        except Exception as exc:
            self._db.rollback()
            failed_case = self._db.get(Case, case_id)
            if failed_case is not None:
                write_audit_log(
                    self._db,
                    case_id=case_id,
                    actor_type="AGENT",
                    actor_id=AgentID.BANKING_ORCHESTRATOR.value,
                    action="ASSESSMENT_FAILED",
                    entity_type="case",
                    entity_id=str(case_id),
                    outcome=AuditOutcome.FAILED,
                    error=type(exc).__name__,
                )
                self._db.commit()
            raise
        return self._manager_required().get(case_id)

    def _build_graph(self):
        builder = StateGraph(OrchestratorState)
        builder.add_node("plan", self._plan_node)
        builder.add_node("specialists", self._specialists_node)
        builder.add_node("missing_data", self._missing_data_node)
        builder.add_node("review", self._review_node)
        builder.add_node("revise", self._revise_node)
        builder.add_node("synthesize", self._synthesize_node)
        builder.add_edge(START, "plan")
        builder.add_edge("plan", "specialists")
        builder.add_conditional_edges(
            "specialists",
            self._route_after_specialists,
            {"missing_data": "missing_data", "review": "review"},
        )
        builder.add_conditional_edges(
            "review",
            lambda state: state["review_route"],
            {"revise": "revise", "synthesize": "synthesize"},
        )
        builder.add_edge("revise", "review")
        builder.add_edge("missing_data", END)
        builder.add_edge("synthesize", END)
        return builder.compile()

    def _plan_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        workflow = self._workflow_required()
        llm = self._llm_factory()
        plan = llm.invoke_structured(
            schema=PlanInterpretation,
            system_prompt=(
                "You are the single Banking Orchestrator. Understand the supplied "
                "corporate loan case and identify analytical focus areas. The workflow "
                "is already bank-approved; do not add agents, skip the human gate, or "
                "make an approval decision."
            ),
            user_prompt=json.dumps(
                {
                    "case_id": str(case.id),
                    "company_name": case.company_name,
                    "requested_amount": str(case.requested_amount),
                    "currency": case.currency,
                    "case_facts": self._case_payload_required(),
                    "workflow": workflow.model_dump(mode="json"),
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        tasks = self._workflow_tasks(workflow)
        repository = self._repository_required()
        board = repository.get_by_case_id(case.id)
        if board is None:
            board = self._manager_required().initialize(
                case.id,
                tasks,
                max_debate_rounds=workflow.max_debate_rounds,
            )
        elif case.status in {
            CaseStatus.AWAITING_DOCS.value,
            CaseStatus.REVISION_REQUESTED.value,
        }:
            board = repository.reset_for_reassessment(
                case.id,
                tasks=tasks,
                max_debate_rounds=workflow.max_debate_rounds,
            )

        case.status = CaseStatus.TIER1_PLANNING.value
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.BANKING_ORCHESTRATOR.value,
            action="TIER1_PLAN",
            entity_type="shared_board",
            entity_id=str(board.board_id),
            response=plan,
        )
        self._db.commit()
        return state

    def _specialists_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        case.status = CaseStatus.TIER2_DEBATING.value
        self._policy_citations = self._retrieve_all_policies()
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.BANKING_ORCHESTRATOR.value,
            action="RAG_QUERY",
            entity_type="case",
            entity_id=str(case.id),
            response={
                agent.value: [str(item.policy_chunk_id) for item in citations]
                for agent, citations in self._policy_citations.items()
            },
        )
        self._db.commit()

        agents = list(POLICY_QUERIES)
        assessments: dict[AgentID, SpecialistAssessment] = {}
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            future_to_agent = {
                executor.submit(
                    self._specialist_runtime.run,
                    agent_id=agent_id,
                    case_payload=self._case_payload_required(),
                    policy_citations=self._policy_citations[agent_id],
                ): agent_id
                for agent_id in agents
            }
            for future in as_completed(future_to_agent):
                agent_id = future_to_agent[future]
                try:
                    assessments[agent_id] = future.result()
                except Exception as exc:
                    assessments[agent_id] = _error_assessment(
                        agent_id,
                        f"Agent execution failed: {type(exc).__name__}",
                    )

        manager = self._manager_required()
        for agent_id in agents:
            board = manager.get(case.id)
            assessment = assessments[agent_id]
            manager.post_assessment(
                case.id,
                assessment,
                expected_version=board.version,
            )
            write_audit_log(
                self._db,
                case_id=case.id,
                actor_type="AGENT",
                actor_id=agent_id.value,
                action="AGENT_OUTPUT_POSTED",
                entity_type="shared_board",
                entity_id=str(board.board_id),
                response=assessment,
            )
            self._db.commit()
        return state

    def _route_after_specialists(
        self, state: OrchestratorState
    ) -> Literal["missing_data", "review"]:
        case_id = UUID(state["case_id"])
        board = self._manager_required().get(case_id)
        if any(
            output.status == AssessmentStatus.REQUIRES_MORE_DATA
            for output in board.specialist_outputs.values()
        ):
            return "missing_data"
        return "review"

    def _missing_data_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        manager = self._manager_required()
        board = manager.get(case.id)
        missing = _unique_missing_data(
            item
            for assessment in board.specialist_outputs.values()
            for item in assessment.missing_data
        )
        replan = replan_for_missing_data(self._llm_factory(), missing)
        updated = board.model_copy(
            update={
                "missing_data": missing,
                "final_summary": {
                    "status": "AWAITING_DOCS",
                    "message": replan.officer_message,
                    "requested_document_types": replan.requested_document_types,
                    "requested_fields": replan.requested_fields,
                    "missing_data": [item.model_dump(mode="json") for item in missing],
                },
            },
            deep=True,
        )
        self._repository_required().save(updated, expected_version=board.version)
        case.status = CaseStatus.AWAITING_DOCS.value
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.BANKING_ORCHESTRATOR.value,
            action="ASSESSMENT_AWAITING_DOCUMENTS",
            entity_type="case",
            entity_id=str(case.id),
            response=missing,
        )
        self._db.commit()
        return state

    def _review_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        manager = self._manager_required()
        board = manager.get(case.id)
        deterministic = self._reviewer.review(board)
        llm = self._llm_factory()
        semantic = llm.invoke_structured(
            schema=SemanticReviewOutput,
            system_prompt=(
                "You are the Reviewer Agent. Find only evidence-backed semantic "
                "contradictions or unsupported cross-domain conclusions in the Shared "
                "Board. Do not duplicate supplied deterministic issues. Do not approve "
                "or reject the loan. Target only one of the five specialist agents."
            ),
            user_prompt=json.dumps(
                {
                    "shared_board": board.model_dump(mode="json"),
                    "deterministic_issues": [
                        issue.model_dump(mode="json") for issue in deterministic.issues
                    ],
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        issues = _deduplicate_issues([*deterministic.issues, *semantic.issues])
        if not issues:
            manager.mark_consensus(case.id, expected_version=board.version)
            write_audit_log(
                self._db,
                case_id=case.id,
                actor_type="AGENT",
                actor_id=AgentID.REVIEWER.value,
                action="CONSENSUS_REACHED",
                entity_type="shared_board",
                entity_id=str(board.board_id),
                response={"review_cycle": board.review_cycle},
            )
            self._db.commit()
            return {**state, "review_route": "synthesize", "revision_targets": []}

        if board.current_debate_round >= board.max_debate_rounds:
            manager.mark_max_rounds_reached(
                case.id,
                expected_version=board.version,
            )
            write_audit_log(
                self._db,
                case_id=case.id,
                actor_type="AGENT",
                actor_id=AgentID.REVIEWER.value,
                action="MAX_DEBATE_ROUNDS_REACHED",
                entity_type="shared_board",
                entity_id=str(board.board_id),
                outcome=AuditOutcome.BLOCKED,
                response=issues,
            )
            self._db.commit()
            return {**state, "review_route": "synthesize", "revision_targets": []}

        next_round = board.current_debate_round + 1
        records = [DebateRecord(round_number=next_round, issue=issue) for issue in issues]
        manager.append_debate_round(
            case.id,
            records,
            expected_version=board.version,
        )
        targets = sorted({issue.target_agent.value for issue in issues})
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.REVIEWER.value,
            action="REVIEW_ISSUES_POSTED",
            entity_type="shared_board",
            entity_id=str(board.board_id),
            response=records,
        )
        self._db.commit()
        return {**state, "review_route": "revise", "revision_targets": targets}

    def _revise_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        manager = self._manager_required()
        targets = [AgentID(value) for value in state.get("revision_targets", [])]
        for agent_id in targets:
            board = manager.get(case.id)
            open_records = [
                record
                for record in board.debate_log
                if record.status.value == "OPEN"
                and record.issue.target_agent == agent_id
                and record.round_number == board.current_debate_round
            ]
            feedback = [record.issue.required_action for record in open_records]
            external_risks = _external_risk_codes(board, exclude=agent_id)
            try:
                assessment = self._specialist_runtime.run(
                    agent_id=agent_id,
                    case_payload=self._case_payload_required(),
                    policy_citations=self._policy_citations[agent_id],
                    reviewer_feedback=feedback,
                    external_risk_codes=external_risks,
                )
            except Exception as exc:
                assessment = _error_assessment(
                    agent_id,
                    f"Agent refinement failed: {type(exc).__name__}",
                )
            board = manager.post_assessment(
                case.id,
                assessment,
                expected_version=board.version,
            )
            for record in open_records:
                board = manager.resolve_debate_issue(
                    case.id,
                    round_number=record.round_number,
                    issue_code=record.issue.code,
                    target_agent=agent_id,
                    specialist_response=assessment.rationale_summary,
                    resolution=(
                        "The target specialist reran with Reviewer feedback; the next "
                        "Reviewer pass will independently verify resolution."
                    ),
                    expected_version=board.version,
                )
            write_audit_log(
                self._db,
                case_id=case.id,
                actor_type="AGENT",
                actor_id=agent_id.value,
                action="AGENT_REFINED",
                entity_type="shared_board",
                entity_id=str(board.board_id),
                response=assessment,
            )
            self._db.commit()
        return state

    def _synthesize_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        manager = self._manager_required()
        board = manager.get(case.id)
        llm = self._llm_factory()
        draft = llm.invoke_structured(
            schema=AssessmentDraft,
            system_prompt=(
                "You are the Banking Orchestrator synthesizing a preliminary corporate "
                "loan assessment for a human officer. Summarize evidence, calculations, "
                "citations, and unresolved debate. Never output an approval/rejection "
                "decision and explicitly state that human verification is required."
            ),
            user_prompt=json.dumps(
                board.model_dump(mode="json"),
                ensure_ascii=False,
                default=str,
            ),
        )
        citation_map = {
            str(citation.policy_chunk_id): citation.model_dump(mode="json")
            for assessment in board.specialist_outputs.values()
            for citation in assessment.policy_citations
        }
        final_summary: dict[str, object] = {
            **draft.model_dump(mode="json"),
            "consensus_reached": board.consensus_reached,
            "review_cycle": board.review_cycle,
            "policy_citations": list(citation_map.values()),
            "human_verification_required": True,
        }
        updated = board.model_copy(
            update={"final_summary": final_summary},
            deep=True,
        )
        self._repository_required().save(updated, expected_version=board.version)
        case.status = CaseStatus.TIER3_PENDING_REVIEW.value
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.BANKING_ORCHESTRATOR.value,
            action="SYNTHESIS_CREATED",
            entity_type="shared_board",
            entity_id=str(board.board_id),
            response=final_summary,
        )
        self._db.commit()
        return state

    def _retrieve_all_policies(self) -> dict[AgentID, list[AgentCitation]]:
        embedding_provider = self._embedding_provider or create_embedding_provider()
        return {
            agent_id: AgentPolicyRetriever(
                self._db,
                agent_id,
                embedding_provider,
            ).retrieve(query, limit=3)
            for agent_id, query in POLICY_QUERIES.items()
        }

    @staticmethod
    def _workflow_tasks(workflow: WorkflowDefinition) -> list[TaskState]:
        return [
            TaskState(
                task_id=step.id,
                assigned_to=step.agent,
                dependencies=[
                    dependency
                    for dependency in step.depends_on
                    if dependency != "understand_and_plan"
                ],
                detail=step.description,
            )
            for step in workflow.steps
            if step.type == WorkflowStepType.SPECIALIST and step.agent is not None
        ]

    def _case_required(self) -> Case:
        if self._case is None:
            raise RuntimeError("Orchestrator case is not initialized")
        return self._case

    def _case_payload_required(self) -> dict[str, object]:
        if self._case_payload is None:
            raise RuntimeError("Orchestrator case payload is not initialized")
        return self._case_payload

    def _build_case_payload(self, case: Case) -> dict[str, object]:
        """Attach parsed case documents without placing customer data in pgvector."""

        remaining = get_settings().agent_document_context_chars
        document_context: list[dict[str, object]] = []
        documents = self._db.scalars(
            select(Document)
            .where(
                Document.case_id == case.id,
                Document.status == DocumentStatus.PARSED.value,
                Document.extracted_text.is_not(None),
            )
            .order_by(Document.created_at)
        ).all()
        for document in documents:
            if remaining <= 0:
                break
            extracted_text = document.extracted_text or ""
            text = extracted_text[:remaining]
            remaining -= len(text)
            document_context.append(
                {
                    "document_id": str(document.id),
                    "document_type": document.document_type,
                    "filename": document.original_filename,
                    "content_type": document.content_type,
                    "content": text,
                    "truncated": len(extracted_text) > len(text),
                }
            )

        payload = dict(case.input_payload)
        payload["canonical_case"] = {
            "case_id": str(case.id),
            "company_name": case.company_name,
            "requested_amount": str(case.requested_amount),
            "currency": case.currency,
        }
        requested_terms = _mapping_copy(payload.get("requested_terms"))
        requested_terms["requested_amount"] = str(case.requested_amount)
        requested_terms["currency"] = case.currency
        payload["requested_terms"] = requested_terms
        borrower_profile = _mapping_copy(payload.get("borrower_profile"))
        borrower_profile["company_name"] = case.company_name
        payload["borrower_profile"] = borrower_profile
        if document_context:
            payload["case_documents"] = document_context
        return payload

    def _workflow_required(self) -> WorkflowDefinition:
        if self._workflow is None:
            raise RuntimeError("Orchestrator workflow is not initialized")
        return self._workflow

    def _repository_required(self) -> SqlSharedBoardRepository:
        if self._repository is None:
            raise RuntimeError("Shared Board repository is not initialized")
        return self._repository

    def _manager_required(self) -> SharedBoardManager:
        if self._manager is None:
            raise RuntimeError("Shared Board manager is not initialized")
        return self._manager


def _error_assessment(agent_id: AgentID, message: str) -> SpecialistAssessment:
    from app.schemas import (
        CollateralAppraisalAssessment,
        CreditAssessment,
        CustomerRelationshipAssessment,
        LegalComplianceAssessment,
        RiskManagementAssessment,
    )

    assessment_types = {
        AgentID.CUSTOMER_RELATIONSHIP: CustomerRelationshipAssessment,
        AgentID.CREDIT: CreditAssessment,
        AgentID.RISK_MANAGEMENT: RiskManagementAssessment,
        AgentID.LEGAL_COMPLIANCE: LegalComplianceAssessment,
        AgentID.COLLATERAL_APPRAISAL: CollateralAppraisalAssessment,
    }
    assessment_type = assessment_types[agent_id]
    return assessment_type(
        status=AssessmentStatus.ERROR,
        error_message=message,
        rationale_summary="The specialist did not produce a valid structured output.",
    )


def _unique_missing_data(
    items: Iterable[MissingDataRequest],
) -> list[MissingDataRequest]:
    unique: dict[str, MissingDataRequest] = {}
    for item in items:
        unique[item.code] = item
    return list(unique.values())


def _deduplicate_issues(issues: Sequence[DebateIssue]) -> list[DebateIssue]:
    unique: dict[tuple[str, AgentID], DebateIssue] = {}
    for issue in issues:
        unique[(issue.code, issue.target_agent)] = issue
    return list(unique.values())


def _external_risk_codes(
    board: SharedBoardState,
    *,
    exclude: AgentID,
) -> list[str]:
    return sorted(
        {
            risk.code
            for agent_id, assessment in board.specialist_outputs.items()
            if agent_id != exclude
            for risk in assessment.risk_flags
            if risk.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL}
        }
    )


def _mapping_copy(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}
