"""Evidence-constrained FPT critic and report narrative synthesis."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from app.agents.income_verification.state import CaseContext
from app.services.case_repository import CaseRepository
from app.services.llm import LLMProvider, LLMProviderError


class CriticOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=20)
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


async def enrich_report_with_fpt(
    context: CaseContext,
    *,
    llm: LLMProvider,
    repository: CaseRepository,
) -> CaseContext:
    """Add narrative only; numeric findings and routing remain deterministic."""

    if context.recommendation is None or not llm.available:
        return context
    payload = {
        "extracted_fields": context.extracted_fields.model_dump(mode="json") if context.extracted_fields else None,
        "income_analysis": context.income_analysis.model_dump(mode="json") if context.income_analysis else None,
        "policy_result": context.policy_result.model_dump(mode="json") if context.policy_result else None,
        "findings": [item.model_dump(mode="json") for item in context.findings],
        "evidence_ids": [item.evidence_id for item in context.evidence],
        "recommendation": context.recommendation.model_dump(mode="json"),
    }
    try:
        critic = await llm.generate_structured(
            CriticOutput,
            system_prompt=(
                "Bạn là Verification/Critic Agent. Kiểm tra mọi kết luận có evidence, "
                "không suy diễn và không phê duyệt/từ chối khoản vay. Không tính lại số; "
                "chỉ dùng số đã có trong JSON. Viết tóm tắt tiếng Việt cho chuyên viên."
            ),
            user_prompt=json.dumps(payload, ensure_ascii=False),
            operation="verification_critic",
        )
    except LLMProviderError:
        context.add_event(
            "LLM_FALLBACK_USED",
            actor_type="VERIFICATION_CRITIC",
            details={"component": "VerificationCritic", "reason": "FPT_LLM_FAILED"},
        )
        return context
    valid_evidence = {item.evidence_id for item in context.evidence}
    unresolved = sorted(set(critic.missing_evidence_ids) - valid_evidence)
    context.recommendation.critic_summary = critic.summary
    context.recommendation.llm_used = True
    context.add_event(
        "LLM_COMPONENT_COMPLETED",
        actor_type="VERIFICATION_CRITIC",
        details={
            "provider": llm.provider_name,
            "model": llm.model_name,
            "unsupported_claim_count": len(critic.unsupported_claims),
            "unresolved_evidence_count": len(unresolved),
        },
    )
    repository.record_agent_result(
        case_id=context.case_id,
        agent_name="VerificationCriticAgent",
        status="SUCCESS",
        result_payload=critic.model_dump(mode="json"),
        llm_provider=llm.provider_name,
        model_name=llm.model_name,
        warnings=critic.warnings + critic.unsupported_claims,
    )
    return context
