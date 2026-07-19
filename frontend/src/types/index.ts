export enum WorkflowState {
  OPEN_CASE = "OPEN_CASE",
  FETCHING_DOCUMENTS = "FETCHING_DOCUMENTS",
  EXTRACTING_DOCUMENT_DATA = "EXTRACTING_DOCUMENT_DATA",
  ANALYZING_INCOME_AND_POLICY = "ANALYZING_INCOME_AND_POLICY",
  CROSS_CHECKING = "CROSS_CHECKING",
  BUILDING_RECOMMENDATION = "BUILDING_RECOMMENDATION",
  HUMAN_REVIEW = "HUMAN_REVIEW",
  PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW", // Used historically/conceptually
  EXECUTING_APPROVED_ACTIONS = "EXECUTING_APPROVED_ACTIONS",
  VERIFYING_EXECUTION = "VERIFYING_EXECUTION",
  COMPLETED = "COMPLETED",
  AWAITING_DOCUMENTS = "AWAITING_DOCUMENTS",
  MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED",
  TECHNICAL_ERROR = "TECHNICAL_ERROR"
}

export enum HumanReviewOutcome {
  ACCEPT_ACTIONS = "ACCEPT_ACTIONS",
  EDIT_AND_RERUN = "EDIT_AND_RERUN",
  MANUAL_HANDLING = "MANUAL_HANDLING"
}

export enum FindingSeverity {
  INFO = "INFO",
  WARNING = "WARNING",
  CRITICAL = "CRITICAL"
}

export interface SalaryTransaction {
  month: string;
  amount: number;
  source: string;
  evidence_id: string;
}

export interface ExtractedData {
  customer_name: string | null;
  declared_income: number | null;
  contract_salary: number | null;
  currency: string;
  employer: string | null;
  salary_transactions: SalaryTransaction[];
  missing_documents: string[];
}

export interface CalculatedIncome {
  average_3_months: number | null;
  average_6_months: number | null;
  qualified_income: number | null;
  is_stable: boolean;
}

export interface Finding {
  id: string;
  type: string;
  severity: FindingSeverity;
  message: string;
  evidence_id: string | null;
}

export interface ProposedAction {
  action_id: string;
  action_type: string;
  description: string;
  parameters: Record<string, any>;
  requires_approval: boolean;
  is_approved?: boolean;
}

export interface DocumentEvidence {
  evidence_id: string;
  document_name: string;
  page_number: number;
  snippet_url?: string;
  raw_text?: string;
}

export interface CaseContext {
  case_id: string;
  application_id: string;
  workflow_state: WorkflowState;
  extracted_data: ExtractedData;
  calculated_income: CalculatedIncome;
  findings: Finding[];
  proposed_actions: ProposedAction[];
  evidence_list: DocumentEvidence[];
  created_at: string;
  updated_at: string;
}

export interface ReviewRequest {
  outcome: HumanReviewOutcome;
  reason: string;
  approved_action_ids: string[];
  edited_qualified_income?: number;
}
