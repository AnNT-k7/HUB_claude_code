export type UUID = string;
export type ISODateTime = string;
export type DecimalString = string;
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export const CASE_STATUSES = ["INGESTED", "TIER1_PLANNING", "AWAITING_DOCS", "TIER2_DEBATING", "TIER3_PENDING_REVIEW", "REVISION_REQUESTED", "APPROVED", "REJECTED", "COMPLETED"] as const;
export type CaseStatus = (typeof CASE_STATUSES)[number];
export type TaskStatus = "PENDING" | "RUNNING" | "COMPLETED" | "REFINING" | "BLOCKED" | "ERROR";
export type AssessmentStatus = "PENDING" | "RUNNING" | "SUCCESS" | "REQUIRES_MORE_DATA" | "MANUAL_REVIEW" | "ERROR";
export const APPROVAL_DECISIONS = ["APPROVED", "REJECTED", "REVISION_REQUESTED"] as const;
export type ApprovalDecision = (typeof APPROVAL_DECISIONS)[number];
export type AgentId = "BankingOrchestrator" | "CustomerRelationship" | "Credit" | "RiskManagement" | "LegalCompliance" | "CollateralAppraisal" | "ReviewerAgent" | "BankingOperations";

export interface CaseCreateRequest { company_name: string; requested_amount: DecimalString; currency: string; input_payload?: Record<string, JsonValue>; }
export interface DocumentMetadata { id: UUID; case_id: UUID; document_type: string; original_filename: string; content_type: string; byte_size: number; sha256: string; status: "UPLOADED" | "PARSED" | "REJECTED"; created_at: ISODateTime; }
export interface CaseSummary { id: UUID; company_name: string; requested_amount: DecimalString; currency: string; status: CaseStatus; workflow_id: string; workflow_version: string; created_at: ISODateTime; updated_at: ISODateTime; }
export interface CaseDetail extends CaseSummary { input_payload: Record<string, JsonValue>; documents: DocumentMetadata[]; }
export type CaseListResponse = CaseSummary[];

export interface AgentCitation { policy_chunk_id: UUID; document_name: string; document_version: string; page_number: number; section_id: string; quote: string; similarity_score?: DecimalString | null; }
export interface CaseDocumentEvidence { document_id: UUID; page_number?: number | null; field_path?: string | null; excerpt: string; }
export interface MissingDataRequest { code: string; description: string; requested_document_types: string[]; requested_fields: string[]; blocking: boolean; }
export interface RiskFlag { code: string; severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"; summary: string; requires_policy_citation: boolean; policy_citations: AgentCitation[]; }

interface SpecialistAssessmentBase { agent_id: AgentId; status: AssessmentStatus; risk_flags: RiskFlag[]; policy_citations: AgentCitation[]; document_evidence: CaseDocumentEvidence[]; missing_data: MissingDataRequest[]; rationale_summary: string; error_message?: string | null; completed_at?: ISODateTime | null; }
export interface CustomerRelationshipAssessment extends SpecialistAssessmentBase { agent_id: "CustomerRelationship"; borrower_profile?: Record<string, JsonValue> | null; requested_terms?: Record<string, JsonValue> | null; }
export interface CreditAssessment extends SpecialistAssessmentBase { agent_id: "Credit"; financial_inputs?: Record<string, JsonValue> | null; calculated_ratios?: { dscr?: DecimalString | null; current_ratio?: DecimalString | null; debt_to_equity?: DecimalString | null } | null; policy_thresholds?: Record<string, JsonValue> | null; acknowledged_cross_domain_risks: string[]; }
export interface RiskManagementAssessment extends SpecialistAssessmentBase { agent_id: "RiskManagement"; risk_tier: "LOW" | "MEDIUM" | "HIGH" | "UNASSIGNED"; concentration_limit_check?: Record<string, JsonValue> | null; industry_risk_summary: string; }
export interface LegalComplianceAssessment extends SpecialistAssessmentBase { agent_id: "LegalCompliance"; legal?: Record<string, JsonValue> | null; compliance?: Record<string, JsonValue> | null; }
export interface CollateralAppraisalAssessment extends SpecialistAssessmentBase { agent_id: "CollateralAppraisal"; requested_loan_amount?: DecimalString | null; collateral_items: Record<string, JsonValue>[]; total_collateral_value?: DecimalString | null; total_eligible_value?: DecimalString | null; computed_ltv_ratio?: DecimalString | null; policy_threshold?: Record<string, JsonValue> | null; }
export type SpecialistAssessment = CustomerRelationshipAssessment | CreditAssessment | RiskManagementAssessment | LegalComplianceAssessment | CollateralAppraisalAssessment;

export interface BoardTask { task_id: string; assigned_to: AgentId; status: TaskStatus; dependencies: string[]; attempts: number; detail: string; updated_at: ISODateTime; }
export type BoardStatus = "INITIALIZED" | "SPECIALISTS_RUNNING" | "DEBATE_IN_PROGRESS" | "CONSENSUS_REACHED" | "MAX_ROUNDS_REACHED";
export interface DebateIssue { code: string; severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"; target_agent: AgentId; description: string; required_action: string; related_field?: string | null; }
export interface DebateLog { round_number: number; critic_agent: "ReviewerAgent"; issue: DebateIssue; status: "OPEN" | "RESOLVED" | "ACCEPTED_FOR_MANUAL_REVIEW"; specialist_response?: string | null; resolution?: string | null; logged_at: ISODateTime; resolved_at?: ISODateTime | null; }
export interface SynthesizedAssessment { executive_summary?: string; overall_risk_level?: "LOW" | "MEDIUM" | "HIGH" | "MANUAL_REVIEW"; key_strengths?: string[]; key_risks?: string[]; officer_attention_items?: string[]; disclaimer?: string; human_verification_required?: boolean; status?: string; message?: string; requested_document_types?: string[]; requested_fields?: string[]; }
export interface SharedBoard { board_id: UUID; case_id: UUID; status: BoardStatus; version: number; tasks: Record<string, BoardTask>; specialist_outputs: Record<string, SpecialistAssessment>; debate_log: DebateLog[]; missing_data: MissingDataRequest[]; final_summary?: SynthesizedAssessment | null; consensus_reached: boolean; current_debate_round: number; review_cycle: number; max_debate_rounds: number; updated_at: ISODateTime; }

export interface ApprovalRecord { id: UUID; case_id: UUID; verified_by: string; decision: ApprovalDecision; feedback: string | null; decided_at: ISODateTime; }
export interface DecisionRequest { decision: ApprovalDecision; feedback: string | null; }
export interface OperationArtifacts { agreement_id: string; onboarding_id: string; request_id: string; agreement_url?: string | null; }
export interface OperationsExecutionResult { id: UUID; case_id: UUID; status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED"; idempotency_key: string; artifacts?: OperationArtifacts | null; created_at: ISODateTime; completed_at?: ISODateTime | null; }
export type AssessmentRunStatus = "QUEUED" | "RUNNING" | "STOP_REQUESTED" | "PAUSED" | "COMPLETED" | "FAILED";
export interface AssessmentRun { id: UUID; case_id: UUID; status: AssessmentRunStatus; current_stage: string; checkpoint_stage: string; stop_requested: boolean; started_by: string; error_message?: string | null; created_at: ISODateTime; started_at?: ISODateTime | null; updated_at: ISODateTime; completed_at?: ISODateTime | null; }
export interface AssessmentEvent { id: number; run_id: UUID; case_id: UUID; event_type: string; stage: string; agent_id?: AgentId | null; status: string; title: string; message: string; evidence: Record<string, JsonValue>; created_at: ISODateTime; }
export interface AssessmentRuntime { run?: AssessmentRun | null; events: AssessmentEvent[]; }
export interface AssessmentStartResponse { case_id: UUID; status: string; run: AssessmentRun; }
export interface PaginatedResponse<T> { items: T[]; total: number; }
