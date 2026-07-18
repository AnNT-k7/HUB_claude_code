---
name: dea-collateral-appraisal
description: Develop or review the Collateral Appraisal Agent for asset evidence, ownership, valuation, liquidity, haircuts, and deterministic LTV analysis. Use when changing collateral_appraisal.py or collateral tools.
---

# Collateral Appraisal Agent

## Role

Extract collateral assets, verify ownership evidence, summarize valuation sources, apply approved haircuts, and calculate the requested-loan LTV for human review.

## Code contract

- Primary module: `backend/app/agents/tier2_board/specialists/collateral_appraisal.py`.
- Preserve `CollateralAppraisalAssessment` fields: `total_collateral_value`, `computed_ltv_ratio`, `collateral_breakdown`, `risk_flags`, and `evidence`.
- Post typed findings to the Shared Board; do not directly instruct Credit or Legal.

## Deterministic analysis

- Calculate total eligible collateral and LTV from structured asset records, requested amount, currency, valuation date, and approved haircuts.
- Never infer market value from a narrative or use stale/uncited valuations silently.
- Guard against duplicate assets, zero collateral, currency mismatch, expired appraisal, and missing ownership documents.

## RAG and evidence

- Query `COLLATERAL` policies with mandatory department and `chunk_type` filters.
- Use `LEGAL_CLAUSE`, `POLICY_RULE`, `STRUCTURED_FACT`, and `CASE_EVIDENCE` chunks as appropriate.
- Cite exact document, page, section, and quote for eligibility, haircut, and LTV conclusions.

## Guardrails

- Collateral reduces risk but does not replace repayment-capacity analysis.
- Do not approve/reject a case or declare title valid without Legal evidence.
- Add deterministic tests for haircuts, duplicate assets, missing values, and LTV boundaries.
