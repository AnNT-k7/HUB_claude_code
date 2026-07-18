"""Strongly typed Tier-2 specialist, debate, and Shared Board contracts."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import ContractModel
from app.schemas.enums import (
    AgentID,
    AmlRiskLevel,
    AssessmentStatus,
    BoardStatus,
    CollateralType,
    DebateStatus,
    KycStatus,
    RiskTier,
    RiskSeverity,
    SPECIALIST_AGENT_IDS,
    TaskStatus,
)
from app.schemas.evidence import (
    AgentCitation,
    CaseDocumentEvidence,
    MissingDataRequest,
    PolicyNumericEvidence,
    RiskFlag,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SpecialistAssessmentBase(ContractModel):
    agent_id: AgentID
    status: AssessmentStatus
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    policy_citations: list[AgentCitation] = Field(default_factory=list)
    document_evidence: list[CaseDocumentEvidence] = Field(default_factory=list)
    missing_data: list[MissingDataRequest] = Field(default_factory=list)
    rationale_summary: str = Field(default="", max_length=4_000)
    error_message: str | None = Field(default=None, min_length=1, max_length=2_000)
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> "SpecialistAssessmentBase":
        if (
            self.status == AssessmentStatus.REQUIRES_MORE_DATA
            and not self.missing_data
        ):
            raise ValueError("REQUIRES_MORE_DATA must include missing_data")
        if self.status == AssessmentStatus.SUCCESS and self.missing_data:
            raise ValueError("SUCCESS cannot include unresolved missing_data")
        if self.status == AssessmentStatus.ERROR and not self.error_message:
            raise ValueError("ERROR must include error_message")
        if self.status != AssessmentStatus.ERROR and self.error_message is not None:
            raise ValueError("error_message is only valid for ERROR assessments")
        if self.status in {
            AssessmentStatus.SUCCESS,
            AssessmentStatus.REQUIRES_MORE_DATA,
            AssessmentStatus.MANUAL_REVIEW,
            AssessmentStatus.ERROR,
        } and self.completed_at is None:
            self.completed_at = utc_now()
        return self


class BorrowerProfile(ContractModel):
    company_name: str = Field(min_length=1, max_length=255)
    registration_number: str = Field(min_length=1, max_length=100)
    industry: str = Field(min_length=1, max_length=255)
    years_in_business: int | None = Field(default=None, ge=0, le=500)
    business_model_summary: str = Field(min_length=1, max_length=4_000)


class RequestedLoanTerms(ContractModel):
    requested_amount: Decimal = Field(gt=0, max_digits=24, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    annual_interest_rate: Decimal | None = Field(
        default=None, ge=0, le=1, max_digits=8, decimal_places=7
    )
    maturity_months: int | None = Field(default=None, ge=1, le=600)


class CustomerRelationshipAssessment(SpecialistAssessmentBase):
    agent_id: Literal[AgentID.CUSTOMER_RELATIONSHIP] = (
        AgentID.CUSTOMER_RELATIONSHIP
    )
    borrower_profile: BorrowerProfile | None = None
    requested_terms: RequestedLoanTerms | None = None


class CreditFinancialInputs(ContractModel):
    cash_available_for_debt_service: Decimal | None = None
    principal_due: Decimal | None = Field(default=None, ge=0)
    interest_due: Decimal | None = Field(default=None, ge=0)
    current_assets: Decimal | None = Field(default=None, ge=0)
    current_liabilities: Decimal | None = Field(default=None, ge=0)
    total_debt: Decimal | None = Field(default=None, ge=0)
    total_equity: Decimal | None = None


class CreditRatios(ContractModel):
    dscr: Decimal | None = None
    current_ratio: Decimal | None = None
    debt_to_equity: Decimal | None = None


class CreditPolicyThresholds(ContractModel):
    minimum_dscr: Decimal | None = Field(default=None, ge=0)
    minimum_current_ratio: Decimal | None = Field(default=None, ge=0)
    maximum_debt_to_equity: Decimal | None = Field(default=None, ge=0)
    citations: list[AgentCitation] = Field(min_length=1)
    threshold_evidence: list[PolicyNumericEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def require_at_least_one_threshold(self) -> "CreditPolicyThresholds":
        if all(
            threshold is None
            for threshold in (
                self.minimum_dscr,
                self.minimum_current_ratio,
                self.maximum_debt_to_equity,
            )
        ):
            raise ValueError("At least one credit threshold is required")
        values = {
            "minimum_dscr": self.minimum_dscr,
            "minimum_current_ratio": self.minimum_current_ratio,
            "maximum_debt_to_equity": self.maximum_debt_to_equity,
        }
        evidence_by_field = {
            item.field_name: item for item in self.threshold_evidence
        }
        if len(evidence_by_field) != len(self.threshold_evidence):
            raise ValueError("Credit threshold evidence fields must be unique")
        citation_ids = {item.policy_chunk_id for item in self.citations}
        for field_name, value in values.items():
            evidence = evidence_by_field.get(field_name)
            if value is None and evidence is not None:
                raise ValueError("Threshold evidence cannot exist without a value")
            if value is not None and (
                evidence is None
                or evidence.value != value
                or evidence.citation.policy_chunk_id not in citation_ids
            ):
                raise ValueError(
                    f"{field_name} must have matching field-level citation evidence"
                )
        return self


class CreditAssessment(SpecialistAssessmentBase):
    agent_id: Literal[AgentID.CREDIT] = AgentID.CREDIT
    financial_inputs: CreditFinancialInputs | None = None
    calculated_ratios: CreditRatios | None = None
    policy_thresholds: CreditPolicyThresholds | None = None
    acknowledged_cross_domain_risks: list[str] = Field(default_factory=list)


class ConcentrationLimitCheck(ContractModel):
    current_exposure: Decimal = Field(ge=0)
    proposed_exposure: Decimal = Field(ge=0)
    policy_limit: Decimal = Field(gt=0)
    within_limit: bool


class RiskManagementAssessment(SpecialistAssessmentBase):
    agent_id: Literal[AgentID.RISK_MANAGEMENT] = AgentID.RISK_MANAGEMENT
    risk_tier: RiskTier = RiskTier.UNASSIGNED
    concentration_limit_check: ConcentrationLimitCheck | None = None
    concentration_policy_evidence: PolicyNumericEvidence | None = None
    industry_risk_summary: str = Field(default="", max_length=4_000)

    @model_validator(mode="after")
    def validate_concentration_evidence(self) -> "RiskManagementAssessment":
        if self.concentration_limit_check is None:
            if self.concentration_policy_evidence is not None:
                raise ValueError("Concentration evidence requires a calculated check")
            return self
        evidence = self.concentration_policy_evidence
        if (
            evidence is None
            or evidence.field_name != "concentration_policy_limit"
            or evidence.value != self.concentration_limit_check.policy_limit
        ):
            raise ValueError("Concentration limit requires matching policy evidence")
        return self


class LegalFindings(ContractModel):
    corporate_governance_valid: bool | None = None
    title_ownership_verified: bool | None = None
    unresolved_litigation: bool | None = None
    litigation_risk_summary: str = Field(default="", max_length=4_000)


class ComplianceFindings(ContractModel):
    kyc_status: KycStatus = KycStatus.UNKNOWN
    aml_risk_level: AmlRiskLevel = AmlRiskLevel.UNKNOWN
    sanctions_check_passed: bool | None = None
    regulatory_inquiry_open: bool | None = None


class LegalComplianceAssessment(SpecialistAssessmentBase):
    """The single authorized agent identity for both legal and compliance work."""

    agent_id: Literal[AgentID.LEGAL_COMPLIANCE] = AgentID.LEGAL_COMPLIANCE
    legal: LegalFindings | None = None
    compliance: ComplianceFindings | None = None


class CollateralItem(ContractModel):
    item_id: str = Field(min_length=1, max_length=100)
    collateral_type: CollateralType
    description: str = Field(min_length=1, max_length=1_000)
    appraised_value: Decimal = Field(ge=0, max_digits=24, decimal_places=4)
    eligible_value: Decimal = Field(ge=0, max_digits=24, decimal_places=4)

    @model_validator(mode="after")
    def validate_eligible_value(self) -> "CollateralItem":
        if self.eligible_value > self.appraised_value:
            raise ValueError("eligible_value cannot exceed appraised_value")
        return self


class CollateralPolicyThreshold(ContractModel):
    maximum_ltv_ratio: Decimal = Field(gt=0)
    citations: list[AgentCitation] = Field(min_length=1)
    threshold_evidence: PolicyNumericEvidence

    @model_validator(mode="after")
    def validate_threshold_evidence(self) -> "CollateralPolicyThreshold":
        if (
            self.threshold_evidence.field_name != "maximum_ltv_ratio"
            or self.threshold_evidence.value != self.maximum_ltv_ratio
            or self.threshold_evidence.citation.policy_chunk_id
            not in {item.policy_chunk_id for item in self.citations}
        ):
            raise ValueError("LTV threshold requires matching field-level evidence")
        return self


class CollateralAppraisalAssessment(SpecialistAssessmentBase):
    agent_id: Literal[AgentID.COLLATERAL_APPRAISAL] = (
        AgentID.COLLATERAL_APPRAISAL
    )
    requested_loan_amount: Decimal | None = Field(default=None, gt=0)
    collateral_items: list[CollateralItem] = Field(default_factory=list)
    total_collateral_value: Decimal | None = Field(default=None, ge=0)
    total_eligible_value: Decimal | None = Field(default=None, ge=0)
    computed_ltv_ratio: Decimal | None = Field(default=None, ge=0)
    policy_threshold: CollateralPolicyThreshold | None = None


SpecialistAssessment: TypeAlias = Annotated[
    CustomerRelationshipAssessment
    | CreditAssessment
    | RiskManagementAssessment
    | LegalComplianceAssessment
    | CollateralAppraisalAssessment,
    Field(discriminator="agent_id"),
]


class TaskState(ContractModel):
    task_id: str = Field(min_length=1, max_length=100)
    assigned_to: AgentID
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = Field(default_factory=list)
    attempts: int = Field(default=0, ge=0)
    detail: str = Field(default="", max_length=2_000)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def require_specialist_assignee(self) -> "TaskState":
        if self.assigned_to not in SPECIALIST_AGENT_IDS:
            raise ValueError("Tier-2 tasks must be assigned to a specialist agent")
        if self.task_id in self.dependencies:
            raise ValueError("A task cannot depend on itself")
        return self


class DebateIssue(ContractModel):
    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    severity: RiskSeverity
    target_agent: AgentID
    description: str = Field(min_length=1, max_length=2_000)
    required_action: str = Field(min_length=1, max_length=2_000)
    related_field: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def require_specialist_target(self) -> "DebateIssue":
        if self.target_agent not in SPECIALIST_AGENT_IDS:
            raise ValueError("Reviewer issues must target a specialist agent")
        return self


class DebateRecord(ContractModel):
    round_number: int = Field(ge=1)
    critic_agent: Literal[AgentID.REVIEWER] = AgentID.REVIEWER
    issue: DebateIssue
    status: DebateStatus = DebateStatus.OPEN
    specialist_response: str | None = Field(default=None, min_length=1, max_length=4_000)
    resolution: str | None = Field(default=None, min_length=1, max_length=4_000)
    logged_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> "DebateRecord":
        if self.status == DebateStatus.RESOLVED and not self.resolution:
            raise ValueError("Resolved debate records require a resolution")
        if self.status == DebateStatus.OPEN and self.resolved_at is not None:
            raise ValueError("Open debate records cannot have resolved_at")
        return self


class SharedBoardState(ContractModel):
    board_id: UUID
    case_id: UUID
    status: BoardStatus = BoardStatus.INITIALIZED
    version: int = Field(default=0, ge=0)
    tasks: dict[str, TaskState] = Field(default_factory=dict)
    specialist_outputs: dict[AgentID, SpecialistAssessment] = Field(
        default_factory=dict
    )
    debate_log: list[DebateRecord] = Field(default_factory=list)
    missing_data: list[MissingDataRequest] = Field(default_factory=list)
    final_summary: dict[str, object] | None = None
    consensus_reached: bool = False
    current_debate_round: int = Field(default=0, ge=0)
    review_cycle: int = Field(default=1, ge=1)
    max_debate_rounds: int = Field(default=3, ge=1, le=10)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_board_invariants(self) -> "SharedBoardState":
        for task_id, task in self.tasks.items():
            if task_id != task.task_id:
                raise ValueError("Task map key must match task.task_id")
            unknown_dependencies = set(task.dependencies) - set(self.tasks)
            if unknown_dependencies:
                raise ValueError(
                    f"Task {task_id} has unknown dependencies: "
                    f"{sorted(unknown_dependencies)}"
                )
        for agent_id, assessment in self.specialist_outputs.items():
            if agent_id != assessment.agent_id:
                raise ValueError(
                    "Specialist output map key must match assessment.agent_id"
                )
            if agent_id not in SPECIALIST_AGENT_IDS:
                raise ValueError("Shared Board accepts only specialist outputs")
        if self.current_debate_round > self.max_debate_rounds:
            raise ValueError("current_debate_round exceeds max_debate_rounds")
        if self.consensus_reached and self.status != BoardStatus.CONSENSUS_REACHED:
            raise ValueError(
                "consensus_reached requires CONSENSUS_REACHED board status"
            )
        if self.status == BoardStatus.CONSENSUS_REACHED and not self.consensus_reached:
            raise ValueError(
                "CONSENSUS_REACHED board status requires consensus_reached"
            )
        return self


class ReviewerResult(ContractModel):
    """Pure Reviewer output; proposed records are persisted by SharedBoardManager."""

    issues: list[DebateIssue] = Field(default_factory=list)
    proposed_debate_records: list[DebateRecord] = Field(default_factory=list)
    consensus_reached: bool = False
    max_rounds_reached: bool = False
    proposed_round: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_review_result(self) -> "ReviewerResult":
        if self.consensus_reached and self.issues:
            raise ValueError("Consensus cannot be reached while issues remain")
        if self.consensus_reached and self.max_rounds_reached:
            raise ValueError("Consensus and max_rounds_reached are mutually exclusive")
        if self.proposed_debate_records and self.proposed_round is None:
            raise ValueError("Proposed debate records require proposed_round")
        if any(
            record.round_number != self.proposed_round
            for record in self.proposed_debate_records
        ):
            raise ValueError("All proposed debate records must use proposed_round")
        return self
