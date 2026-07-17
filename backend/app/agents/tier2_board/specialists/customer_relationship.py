"""
Tier 2 Specialist — Customer Relationship Agent.

Department: Customer Relationship Department
Responsibilities:
  - Extract general borrower profile and company history from uploaded proposal documents
  - Parse requested term sheet parameters (loan amount, requested currency, interest rate, maturity)
  - Summarize business model, key revenue drivers, and primary customer base
  - Post structured SpecialistAssessment to the Shared Board
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field


class CustomerRelationshipAssessment(BaseModel):
    agent_id: str = "CustomerRelationship"
    status: str = "PENDING"
    borrower_profile: Dict[str, Any] = Field(default_factory=dict)
    requested_terms: Dict[str, Any] = Field(default_factory=dict)
    business_model_summary: str = ""
    risk_flags: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)

# TODO: Implement LangChain tool definitions and LangGraph node runner for Customer Relationship Agent
