from __future__ import annotations

import json

from pydantic import Field

from app.schemas import MissingDataRequest
from app.schemas.base import ContractModel
from app.services.llm import StructuredLLM


class ReplanProposal(ContractModel):
    officer_message: str = Field(min_length=1, max_length=3_000)
    requested_document_types: list[str] = Field(default_factory=list)
    requested_fields: list[str] = Field(default_factory=list)


def replan_for_missing_data(
    llm: StructuredLLM,
    missing_data: list[MissingDataRequest],
) -> ReplanProposal:
    """Ask Tier-1 to consolidate explicit requests without inventing inputs."""

    proposal = llm.invoke_structured(
        schema=ReplanProposal,
        system_prompt=(
            "You are the Banking Orchestrator replanning a paused assessment. "
            "Consolidate only the supplied missing-data requests into a clear message "
            "for the banking officer. Do not infer values or approve/reject the case."
        ),
        user_prompt=json.dumps(
            [item.model_dump(mode="json") for item in missing_data],
            ensure_ascii=False,
        ),
    )
    allowed_documents = {
        document_type
        for item in missing_data
        for document_type in item.requested_document_types
    }
    allowed_fields = {
        field_name for item in missing_data for field_name in item.requested_fields
    }
    if not set(proposal.requested_document_types) <= allowed_documents:
        raise ValueError("Replanner requested an unsupported document type")
    if not set(proposal.requested_fields) <= allowed_fields:
        raise ValueError("Replanner requested an unsupported field")
    return proposal
