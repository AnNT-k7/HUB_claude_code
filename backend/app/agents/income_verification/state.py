"""Typed state contracts for the Income Verification Expert workflow."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class WorkflowState(StrEnum):
    OPEN_CASE = "OPEN_CASE"
    FETCHING_DOCUMENTS = "FETCHING_DOCUMENTS"
    EXTRACTING_DOCUMENT_DATA = "EXTRACTING_DOCUMENT_DATA"
    ANALYZING_INCOME_AND_POLICY = "ANALYZING_INCOME_AND_POLICY"
    CROSS_CHECKING = "CROSS_CHECKING"
    BUILDING_RECOMMENDATION = "BUILDING_RECOMMENDATION"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    EXECUTING_APPROVED_ACTIONS = "EXECUTING_APPROVED_ACTIONS"
    VERIFYING_EXECUTION = "VERIFYING_EXECUTION"
    COMPLETED = "COMPLETED"
    AWAITING_DOCUMENTS = "AWAITING_DOCUMENTS"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    TECHNICAL_ERROR = "TECHNICAL_ERROR"


class TaskType(StrEnum):
    INCOME_VERIFICATION = "INCOME_VERIFICATION"


class ComponentStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    MISSING_DATA = "MISSING_DATA"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ERROR = "ERROR"


class VerificationResultStatus(StrEnum):
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    MISSING_DOCUMENTS = "MISSING_DOCUMENTS"
    POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    TECHNICAL_ERROR = "TECHNICAL_ERROR"
    COMPLETED = "COMPLETED"


class FindingSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ActionPermission(StrEnum):
    AUTO_REVERSIBLE = "AUTO_REVERSIBLE"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    PROHIBITED = "PROHIBITED"


class ActionType(StrEnum):
    UPDATE_INCOME_DRAFT = "UPDATE_INCOME_DRAFT"
    REQUEST_DOCUMENTS = "REQUEST_DOCUMENTS"
    CREATE_EXCEPTION_TASK = "CREATE_EXCEPTION_TASK"
    ATTACH_EVIDENCE = "ATTACH_EVIDENCE"


class HumanReviewOutcome(StrEnum):
    ACCEPT_ACTIONS = "ACCEPT_ACTIONS"
    EDIT_AND_RERUN = "EDIT_AND_RERUN"
    MANUAL_HANDLING = "MANUAL_HANDLING"


class ExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    DUPLICATE = "DUPLICATE"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class DocumentStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNREADABLE = "UNREADABLE"
    MISSING = "MISSING"


class IncomeVerificationModel(BaseModel):
    """Base model with strict runtime validation for workflow contracts."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class DocumentRecord(IncomeVerificationModel):
    document_id: str = Field(min_length=1)
    document_name: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    checksum: str = Field(min_length=1)
    status: DocumentStatus = DocumentStatus.AVAILABLE
    content_type: str = "application/octet-stream"
    page_count: int | None = Field(default=None, ge=1)
    processing_status: str = "UPLOADED"
    size_bytes: int = Field(default=0, ge=0)


class EvidenceCitation(IncomeVerificationModel):
    evidence_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_name: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    section_id: str | None = None
    quote: str = Field(min_length=1)
    source_checksum: str | None = None
    location: str | None = None
    field_name: str = "unknown"
    confidence: float = Field(default=1.0, ge=0, le=1)
    extraction_method: str = "unknown"


class PolicyCitation(IncomeVerificationModel):
    document_name: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    section_id: str = Field(min_length=1)
    effective_date: date
    quote: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)


class SalaryTransaction(IncomeVerificationModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    source: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class VariableIncomeRecord(IncomeVerificationModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    evidence_id: str = Field(min_length=1)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ExtractedFields(IncomeVerificationModel):
    customer_name: str | None = None
    declared_income: Decimal | None = Field(default=None, ge=0)
    contract_salary: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(min_length=3, max_length=3)
    employer: str | None = None
    contract_expiry: date | None = None
    salary_transactions: list[SalaryTransaction] = Field(default_factory=list)
    variable_income_records: list[VariableIncomeRecord] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0, le=1)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class DocumentExtractionResult(IncomeVerificationModel):
    status: ComponentStatus
    extracted_fields: ExtractedFields | None = None
    evidence: list[EvidenceCitation] = Field(default_factory=list)
    reason_code: str | None = None


class IncomeAnomaly(IncomeVerificationModel):
    code: str = Field(min_length=1)
    month: str | None = None
    amount: Decimal | None = None
    deviation_ratio: Decimal | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class IncomeAnalysisResult(IncomeVerificationModel):
    status: ComponentStatus
    average_income: Decimal | None = Field(default=None, ge=0)
    variation_ratio: Decimal | None = Field(default=None, ge=0)
    period_count: int = Field(default=0, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    recognized_evidence_ids: list[str] = Field(default_factory=list)
    excluded_evidence_reasons: dict[str, str] = Field(default_factory=dict)
    calculation_version: str | None = None
    input_fact_ids: list[str] = Field(default_factory=list)
    anomalies: list[IncomeAnomaly] = Field(default_factory=list)
    reason_code: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_optional_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class PolicyResult(IncomeVerificationModel):
    status: ComponentStatus
    eligible_income: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    required_documents: list[str] = Field(default_factory=list)
    required_statement_months: int | None = Field(default=None, ge=1)
    applied_rule_ids: list[str] = Field(default_factory=list)
    citations: list[PolicyCitation] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    average_documented_variable_income: Decimal | None = Field(default=None, ge=0)
    variable_income_cap: Decimal | None = Field(default=None, ge=0)
    calculation_version: str | None = None
    input_fact_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_optional_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


FlatValue = str | int | float | bool | None


class Finding(IncomeVerificationModel):
    finding_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    severity: FindingSeverity
    message: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    source_values: dict[str, FlatValue] = Field(default_factory=dict)
    rule_version: str = Field(min_length=1)


class ProposedAction(IncomeVerificationModel):
    action_id: str = Field(min_length=1)
    action_type: ActionType
    description: str = Field(min_length=1)
    parameters: dict[str, FlatValue] = Field(default_factory=dict)
    permission: ActionPermission
    evidence_ids: list[str] = Field(default_factory=list)


class Recommendation(IncomeVerificationModel):
    status: VerificationResultStatus
    summary: str = Field(min_length=1)
    declared_income: Decimal | None = None
    average_income: Decimal | None = None
    eligible_income: Decimal | None = None
    currency: str | None = None
    findings: list[Finding] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    policy_citations: list[PolicyCitation] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    critic_summary: str | None = None
    llm_used: bool = False


class HumanReviewRecord(IncomeVerificationModel):
    reviewer_id: str = Field(min_length=1)
    outcome: HumanReviewOutcome
    reason: str = Field(min_length=1)
    approved_action_ids: list[str] = Field(default_factory=list)
    edited_values: dict[str, FlatValue] = Field(default_factory=dict)
    reviewed_at: datetime = Field(default_factory=utc_now)


class ExecutionResult(IncomeVerificationModel):
    action_id: str = Field(min_length=1)
    status: ExecutionStatus
    idempotency_key: str = Field(min_length=1)
    result_reference: str | None = None
    verified: bool = False
    reason_code: str | None = None
    executed_at: datetime = Field(default_factory=utc_now)


class WorkflowError(IncomeVerificationModel):
    code: str = Field(min_length=1)
    component: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool
    attempt: int = Field(ge=1)
    occurred_at: datetime = Field(default_factory=utc_now)


class AuditEvent(IncomeVerificationModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str = Field(min_length=1)
    actor_type: str = Field(min_length=1)
    actor_id: str | None = None
    from_state: WorkflowState | None = None
    to_state: WorkflowState | None = None
    details: dict[str, FlatValue] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class InvalidStateTransition(ValueError):
    """Raised when a workflow attempts an unapproved transition."""


class CaseContext(IncomeVerificationModel):
    """Versioned, case-scoped shared state for the income workflow."""

    ALLOWED_TRANSITIONS: ClassVar[dict[WorkflowState, set[WorkflowState]]] = {
        WorkflowState.OPEN_CASE: {WorkflowState.FETCHING_DOCUMENTS},
        WorkflowState.FETCHING_DOCUMENTS: {
            WorkflowState.EXTRACTING_DOCUMENT_DATA,
            WorkflowState.AWAITING_DOCUMENTS,
            WorkflowState.MANUAL_REVIEW_REQUIRED,
        },
        WorkflowState.EXTRACTING_DOCUMENT_DATA: {
            WorkflowState.ANALYZING_INCOME_AND_POLICY,
            WorkflowState.AWAITING_DOCUMENTS,
            WorkflowState.MANUAL_REVIEW_REQUIRED,
        },
        WorkflowState.ANALYZING_INCOME_AND_POLICY: {
            WorkflowState.CROSS_CHECKING,
            WorkflowState.MANUAL_REVIEW_REQUIRED,
        },
        WorkflowState.CROSS_CHECKING: {
            WorkflowState.BUILDING_RECOMMENDATION,
            WorkflowState.MANUAL_REVIEW_REQUIRED,
        },
        WorkflowState.BUILDING_RECOMMENDATION: {
            WorkflowState.HUMAN_REVIEW,
            WorkflowState.MANUAL_REVIEW_REQUIRED,
        },
        WorkflowState.HUMAN_REVIEW: {
            WorkflowState.BUILDING_RECOMMENDATION,
            WorkflowState.EXECUTING_APPROVED_ACTIONS,
            WorkflowState.MANUAL_REVIEW_REQUIRED,
        },
        WorkflowState.EXECUTING_APPROVED_ACTIONS: {
            WorkflowState.VERIFYING_EXECUTION,
            WorkflowState.TECHNICAL_ERROR,
        },
        WorkflowState.VERIFYING_EXECUTION: {WorkflowState.COMPLETED},
        WorkflowState.AWAITING_DOCUMENTS: {WorkflowState.FETCHING_DOCUMENTS},
        WorkflowState.MANUAL_REVIEW_REQUIRED: {
            WorkflowState.FETCHING_DOCUMENTS,
            WorkflowState.BUILDING_RECOMMENDATION,
        },
        WorkflowState.TECHNICAL_ERROR: {
            WorkflowState.EXECUTING_APPROVED_ACTIONS
        },
        WorkflowState.COMPLETED: set(),
    }

    case_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    task_type: TaskType = TaskType.INCOME_VERIFICATION
    workflow_state: WorkflowState = WorkflowState.OPEN_CASE
    state_version: int = Field(default=0, ge=0)
    workflow_version: str = "income-verification-v1"
    runtime_mode: str = "DETERMINISTIC_FALLBACK"
    documents: list[DocumentRecord] = Field(default_factory=list)
    extracted_fields: ExtractedFields | None = None
    income_analysis: IncomeAnalysisResult | None = None
    policy_result: PolicyResult | None = None
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[EvidenceCitation] = Field(default_factory=list)
    recommendation: Recommendation | None = None
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    human_review: HumanReviewRecord | None = None
    execution_results: list[ExecutionResult] = Field(default_factory=list)
    errors: list[WorkflowError] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def add_event(
        self,
        event_type: str,
        *,
        actor_type: str = "SYSTEM",
        actor_id: str | None = None,
        details: dict[str, FlatValue] | None = None,
    ) -> None:
        self.audit_events.append(
            AuditEvent(
                event_type=event_type,
                actor_type=actor_type,
                actor_id=actor_id,
                details=details or {},
            )
        )
        self._touch()

    def add_error(self, error: WorkflowError) -> None:
        self.errors.append(error)
        self._touch()

    def transition_to(
        self,
        next_state: WorkflowState,
        *,
        event_type: str = "STATE_TRANSITION",
        details: dict[str, FlatValue] | None = None,
    ) -> None:
        allowed = self.ALLOWED_TRANSITIONS[self.workflow_state]
        if next_state not in allowed:
            raise InvalidStateTransition(
                f"Transition {self.workflow_state} -> {next_state} is not allowed"
            )

        previous_state = self.workflow_state
        self.workflow_state = next_state
        self.audit_events.append(
            AuditEvent(
                event_type=event_type,
                actor_type="ORCHESTRATOR",
                from_state=previous_state,
                to_state=next_state,
                details=details or {},
            )
        )
        self._touch()

    def _touch(self) -> None:
        self.state_version += 1
        self.updated_at = utc_now()
