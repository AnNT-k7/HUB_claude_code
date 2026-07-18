from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class WorkflowState(str, Enum):
    INIT = "INIT"
    FETCHING_DOCUMENTS = "FETCHING_DOCUMENTS"
    EXTRACTING_DATA = "EXTRACTING_DATA"
    ANALYZING_INCOME_AND_POLICY = "ANALYZING_INCOME_AND_POLICY"
    CHECKING_CONSISTENCY = "CHECKING_CONSISTENCY"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    EXECUTING_ACTIONS = "EXECUTING_ACTIONS"
    COMPLETED = "COMPLETED"

class HumanReviewOutcome(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"

class FindingSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class SalaryTransaction(BaseModel):
    month: str
    amount: float
    source: str
    evidence_id: str

class ExtractedData(BaseModel):
    customer_name: Optional[str] = None
    declared_income: Optional[float] = None
    contract_salary: Optional[float] = None
    currency: str = "VND"
    employer: Optional[str] = None
    salary_transactions: List[SalaryTransaction] = []
    missing_documents: List[str] = []

class CalculatedIncome(BaseModel):
    average_3_months: Optional[float] = None
    average_6_months: Optional[float] = None
    qualified_income: Optional[float] = None
    is_stable: bool = False

class Finding(BaseModel):
    id: str
    type: str
    severity: FindingSeverity
    message: str
    evidence_id: Optional[str] = None

class ProposedAction(BaseModel):
    action_id: str
    action_type: str
    description: str
    parameters: Dict[str, Any] = {}
    requires_approval: bool = True
    is_approved: Optional[bool] = None

class DocumentEvidence(BaseModel):
    evidence_id: str
    document_name: str
    page_number: int
    snippet_url: Optional[str] = None
    raw_text: Optional[str] = None

class CaseContextResponse(BaseModel):
    case_id: str
    application_id: str
    workflow_state: WorkflowState
    extracted_data: ExtractedData
    calculated_income: CalculatedIncome
    findings: List[Finding] = []
    proposed_actions: List[ProposedAction] = []
    evidence_list: List[DocumentEvidence] = []
    created_at: datetime
    updated_at: datetime

class ReviewRequest(BaseModel):
    outcome: HumanReviewOutcome
    reason: str
    approved_action_ids: List[str] = []
    edited_qualified_income: Optional[float] = None

class ReviewResponse(BaseModel):
    message: str
    next_state: str

class StartWorkflowResponse(BaseModel):
    case_id: str
    workflow_state: str
