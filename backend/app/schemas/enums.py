"""Canonical enum values for the multi-agent collaboration contracts."""

from enum import Enum


class AgentID(str, Enum):
    BANKING_ORCHESTRATOR = "BankingOrchestrator"
    CUSTOMER_RELATIONSHIP = "CustomerRelationship"
    CREDIT = "Credit"
    RISK_MANAGEMENT = "RiskManagement"
    LEGAL_COMPLIANCE = "LegalCompliance"
    COLLATERAL_APPRAISAL = "CollateralAppraisal"
    REVIEWER = "ReviewerAgent"
    BANKING_OPERATIONS = "BankingOperations"


SPECIALIST_AGENT_IDS: frozenset[AgentID] = frozenset(
    {
        AgentID.CUSTOMER_RELATIONSHIP,
        AgentID.CREDIT,
        AgentID.RISK_MANAGEMENT,
        AgentID.LEGAL_COMPLIANCE,
        AgentID.COLLATERAL_APPRAISAL,
    }
)


class AssessmentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    REQUIRES_MORE_DATA = "REQUIRES_MORE_DATA"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ERROR = "ERROR"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    REFINING = "REFINING"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


class BoardStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    SPECIALISTS_RUNNING = "SPECIALISTS_RUNNING"
    DEBATE_IN_PROGRESS = "DEBATE_IN_PROGRESS"
    CONSENSUS_REACHED = "CONSENSUS_REACHED"
    MAX_ROUNDS_REACHED = "MAX_ROUNDS_REACHED"


class DebateStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    ACCEPTED_FOR_MANUAL_REVIEW = "ACCEPTED_FOR_MANUAL_REVIEW"


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNASSIGNED = "UNASSIGNED"


class KycStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class AmlRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class CollateralType(str, Enum):
    REAL_ESTATE = "REAL_ESTATE"
    EQUIPMENT = "EQUIPMENT"
    INVENTORY = "INVENTORY"
    CASH = "CASH"
    OTHER = "OTHER"


class CaseStatus(str, Enum):
    INGESTED = "INGESTED"
    TIER1_PLANNING = "TIER1_PLANNING"
    AWAITING_DOCS = "AWAITING_DOCS"
    TIER2_DEBATING = "TIER2_DEBATING"
    TIER3_PENDING_REVIEW = "TIER3_PENDING_REVIEW"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PARSED = "PARSED"
    REJECTED = "REJECTED"


class OperationStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
