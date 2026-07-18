export type UUID = string;
export type ISODateTime = string;
export type DecimalString = string;

export const CASE_STATUSES = [
  "INGESTED",
  "TIER1_PLANNING",
  "AWAITING_DOCS",
  "TIER2_DEBATING",
  "TIER3_PENDING_REVIEW",
  "REVISION_REQUESTED",
  "APPROVED",
  "REJECTED",
  "COMPLETED",
  "FAILED",
] as const;

export type CaseStatus = (typeof CASE_STATUSES)[number];

export const TASK_STATUSES = [
  "PENDING",
  "RUNNING",
  "COMPLETED",
  "REFINING",
  "BLOCKED",
  "ERROR",
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

export const ASSESSMENT_STATUSES = [
  "PENDING",
  "RUNNING",
  "SUCCESS",
  "REQUIRES_MORE_DATA",
  "MANUAL_REVIEW",
  "ERROR",
] as const;

export type AssessmentStatus = (typeof ASSESSMENT_STATUSES)[number];

export const APPROVAL_DECISIONS = [
  "APPROVED",
  "REJECTED",
  "REVISION_REQUESTED",
] as const;

export type ApprovalDecision = (typeof APPROVAL_DECISIONS)[number];

export type AgentId =
  | "CustomerRelationship"
  | "Credit"
  | "RiskManagement"
  | "LegalCompliance"
  | "Compliance"
  | "Legal"
  | "CollateralAppraisal"
  | "Reviewer"
  | "BankingOperations";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue =
  | JsonPrimitive
  | JsonValue[]
  | { readonly [key: string]: JsonValue };

export interface CaseCreateRequest {
  company_name: string;
  requested_amount: DecimalString;
  currency: string;
}

export interface DocumentMetadata {
  id: UUID;
  case_id: UUID;
  filename: string;
  content_type: string;
  size_bytes: number;
  status?: "UPLOADING" | "STORED" | "FAILED";
  uploaded_at?: ISODateTime;
  created_at?: ISODateTime;
}

export interface CaseSummary {
  id: UUID;
  company_name: string;
  requested_amount: DecimalString;
  currency: string;
  status: CaseStatus;
  created_at: ISODateTime;
  document_count?: number;
}

export interface ApprovalRecord {
  id: UUID;
  case_id: UUID;
  verified_by: string;
  decision: ApprovalDecision;
  feedback: string | null;
  decided_at: ISODateTime;
}

export interface CaseDetail extends CaseSummary {
  documents: DocumentMetadata[];
  approval?: ApprovalRecord | null;
}

export interface PaginatedResponse<TItem> {
  items: TItem[];
  total: number;
  page?: number;
  page_size?: number;
}

export type CaseListResponse = CaseSummary[] | PaginatedResponse<CaseSummary>;

export interface AgentCitation {
  policy_chunk_id?: UUID;
  document_id?: UUID;
  document_name: string;
  document_version?: string;
  page_number: number;
  section_id: string;
  quote: string;
  source_url?: string;
}

export interface CaseDocumentEvidence {
  document_id: UUID;
  filename?: string;
  page_number?: number | null;
  field_path?: string | null;
  excerpt: string;
}

export interface MissingDataRequest {
  document_type: string;
  reason: string;
  required_fields?: string[];
}

interface SpecialistAssessmentBase {
  agent_id: AgentId;
  status: AssessmentStatus;
  risk_flags: string[];
  evidence: AgentCitation[];
  document_evidence?: CaseDocumentEvidence[];
  missing_data?: MissingDataRequest[];
  rationale_summary?: string;
  key_findings?: Readonly<Record<string, JsonValue>>;
}

export interface CustomerRelationshipAssessment
  extends SpecialistAssessmentBase {
  agent_id: "CustomerRelationship";
  borrower_profile: Readonly<Record<string, JsonValue>>;
  requested_terms: Readonly<Record<string, JsonValue>>;
  business_model_summary: string;
}

export interface CreditAssessment extends SpecialistAssessmentBase {
  agent_id: "Credit";
  calculated_ratios: Readonly<Record<string, number>>;
  cash_flow_viability: string;
}

export interface RiskManagementAssessment extends SpecialistAssessmentBase {
  agent_id: "RiskManagement";
  risk_tier: "LOW" | "MEDIUM" | "HIGH" | "UNASSIGNED";
  concentration_limit_check: Readonly<Record<string, JsonValue>>;
  industry_risk_analysis: string;
}

export interface ComplianceAssessment extends SpecialistAssessmentBase {
  agent_id: "Compliance";
  kyc_status: "VERIFIED" | "UNVERIFIED" | "FAILED";
  aml_risk_level: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
  sanctions_check_passed: boolean;
}

export interface LegalAssessment extends SpecialistAssessmentBase {
  agent_id: "Legal";
  corporate_governance_valid: boolean;
  title_ownership_verified: boolean;
  litigation_risk_summary: string;
}

export interface LegalComplianceAssessment extends SpecialistAssessmentBase {
  agent_id: "LegalCompliance";
  kyc_status?: "VERIFIED" | "UNVERIFIED" | "FAILED";
  aml_risk_level?: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
  sanctions_check_passed?: boolean;
  corporate_governance_valid?: boolean;
  title_ownership_verified?: boolean;
  litigation_risk_summary?: string;
}

export interface CollateralAppraisalAssessment
  extends SpecialistAssessmentBase {
  agent_id: "CollateralAppraisal";
  total_collateral_value: number;
  computed_ltv_ratio: number;
  collateral_breakdown: ReadonlyArray<Readonly<Record<string, JsonValue>>>;
}

export type SpecialistAssessment =
  | CustomerRelationshipAssessment
  | CreditAssessment
  | RiskManagementAssessment
  | ComplianceAssessment
  | LegalAssessment
  | LegalComplianceAssessment
  | CollateralAppraisalAssessment;

export interface BoardTask {
  status: TaskStatus;
  assigned_to: AgentId;
  description?: string;
  error_message?: string | null;
}

export type BoardStatus =
  | "INITIALIZED"
  | "PLANNING"
  | "DEBATE_IN_PROGRESS"
  | "CONSENSUS_REACHED"
  | "REQUIRES_MORE_DATA"
  | "MAX_ROUNDS_REACHED";

export interface SynthesizedAssessment {
  executive_summary: string;
  recommendation: "PROCEED_TO_REVIEW" | "MANUAL_REVIEW" | "REQUIRES_MORE_DATA";
  key_strengths: string[];
  key_risks: string[];
  conditions?: string[];
}

export interface SharedBoard {
  id: UUID;
  case_id: UUID;
  status?: BoardStatus;
  task_breakdown: Readonly<Record<string, BoardTask>>;
  specialist_outputs: Readonly<Record<string, SpecialistAssessment>>;
  consensus_reached: boolean;
  current_debate_round: number;
  max_debate_rounds?: number;
  final_synthesis?: SynthesizedAssessment | null;
  updated_at: ISODateTime;
}

export interface DebateLog {
  id: UUID;
  case_id: UUID;
  round_number: number;
  critic_agent: string;
  target_agent: string;
  error_identified: string;
  resolution_applied: string | null;
  logged_at: ISODateTime;
}

export interface DecisionRequest {
  decision: ApprovalDecision;
  feedback: string | null;
}

export interface OperationsExecutionResult {
  agent_id: "BankingOperations";
  case_id: UUID;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  generated_agreement_url: string;
  onboarding_payload: Readonly<Record<string, JsonValue>>;
  mock_api_responses: Readonly<Record<string, JsonValue>>;
  audit_trace_id: UUID | string;
}

export interface AssessmentStartResponse {
  case_id: UUID;
  status: CaseStatus;
  message?: string;
}
