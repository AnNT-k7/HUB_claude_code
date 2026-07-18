"""Evidence, citation, and missing-data contracts used by every agent."""

from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import ContractModel
from app.schemas.enums import RiskSeverity


class AgentCitation(ContractModel):
    """Exact, versioned citation to an approved internal policy chunk."""

    policy_chunk_id: UUID
    document_name: str = Field(min_length=1, max_length=255)
    document_version: str = Field(min_length=1, max_length=64)
    page_number: int = Field(ge=1)
    section_id: str = Field(min_length=1, max_length=128)
    quote: str = Field(min_length=1, max_length=2_000)
    similarity_score: Decimal | None = Field(default=None, ge=-1, le=1)


class PolicyNumericEvidence(ContractModel):
    """A numeric policy value bound to one exact, validated RAG citation."""

    field_name: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    value: Decimal = Field(gt=0)
    citation: AgentCitation
    supporting_quote: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def quote_must_come_from_citation(self) -> "PolicyNumericEvidence":
        normalized_support = " ".join(self.supporting_quote.split()).casefold()
        normalized_source = " ".join(self.citation.quote.split()).casefold()
        if normalized_support not in normalized_source:
            raise ValueError("supporting_quote must be contained in the cited chunk")
        return self


class CaseDocumentEvidence(ContractModel):
    """Traceable evidence from a case document; never a policy citation."""

    document_id: UUID
    page_number: int | None = Field(default=None, ge=1)
    field_path: str | None = Field(default=None, min_length=1, max_length=255)
    excerpt: str = Field(min_length=1, max_length=2_000)


class MissingDataRequest(ContractModel):
    """A concrete data request emitted instead of guessing a value."""

    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    description: str = Field(min_length=1, max_length=1_000)
    requested_document_types: list[str] = Field(default_factory=list)
    requested_fields: list[str] = Field(default_factory=list)
    blocking: bool = True

    @model_validator(mode="after")
    def require_actionable_request(self) -> "MissingDataRequest":
        if not self.requested_document_types and not self.requested_fields:
            raise ValueError(
                "A missing-data request must identify a document type or field"
            )
        return self


class RiskFlag(ContractModel):
    """Structured risk signal with explicit policy-citation requirements."""

    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z][A-Z0-9_]*$")
    severity: RiskSeverity
    summary: str = Field(min_length=1, max_length=2_000)
    requires_policy_citation: bool = True
    policy_citations: list[AgentCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_required_citations(self) -> "RiskFlag":
        if self.requires_policy_citation and not self.policy_citations:
            raise ValueError("Policy-driven risk flags require at least one citation")
        return self
