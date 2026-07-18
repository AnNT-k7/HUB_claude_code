---
name: dea-risk-management
description: Develop or review the Risk Management Agent for industry risk, concentration limits, exposure controls, and preliminary risk tiers backed by policy evidence. Use when changing risk_management.py or risk tools.
---

# Risk Management Agent

## Role

Independently assess industry/macroeconomic risk, borrower exposure, concentration limits, and policy constraints. Produce a preliminary risk tier with explicit rationale.

## Code contract

- Primary module: `backend/app/agents/tier2_board/specialists/risk_management.py`.
- Preserve `RiskManagementAssessment` fields: `risk_tier`, `concentration_limit_check`, `industry_risk_analysis`, `risk_flags`, and `evidence`.
- Read other findings through the Shared Board; do not send direct specialist messages.

## Evidence and RAG

- Query `RISK` policies with mandatory department and `chunk_type` filters.
- Prefer `POLICY_RULE`, `CASE_EVIDENCE`, and structured exposure facts.
- Every tier or limit conclusion needs document, page, section, and quote evidence.
- Missing industry, exposure, or limit data means manual review, not a guessed tier.

## Guardrails

- Risk tier is advisory and cannot approve/reject the case.
- Keep policy limits configurable and sourced from RAG; do not bury them in prompts.
- Test boundary conditions, missing exposures, and conflicting evidence deterministically.
