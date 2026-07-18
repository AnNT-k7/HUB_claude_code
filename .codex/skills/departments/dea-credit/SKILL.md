---
name: dea-credit
description: Develop or review the Credit Agent for financial statement analysis, deterministic DSCR/current-ratio/leverage calculations, and policy-backed credit findings. Use when changing credit.py, financial tools, or credit evidence contracts.
---

# Credit Agent

## Role

Analyze balance sheet, income statement, cash flow, debt obligations, and repayment sources. Produce reproducible financial metrics and policy comparisons for human review.

## Code contract

- Primary module: `backend/app/agents/tier2_board/specialists/credit.py`.
- Preserve `CreditAssessment` fields: `calculated_ratios`, `cash_flow_viability`, `risk_flags`, and `evidence`.
- Financial facts must be structured and traceable to `case_id` and source pages.

## Deterministic analysis

- Calculate DSCR, Current Ratio, and Leverage (D/E) in a tested Python tool from structured facts.
- Never ask an LLM to add, divide, infer missing periods, or silently convert currencies.
- Record formula inputs, period, currency, rounding policy, and source citations.
- If a required fact or debt-service definition is absent, return incomplete/manual review instead of estimating.

## RAG and review

- Query `CREDIT` policies with mandatory department and `chunk_type` filters.
- Use `STRUCTURED_FACT`, `POLICY_RULE`, and relevant `CASE_EVIDENCE` chunks.
- Compare metrics with retrieved thresholds and quote exact policy evidence; do not hardcode thresholds in prompts.
- Post structured output to the Shared Board for Reviewer cross-checking.

## Guardrails

- Do not approve/reject a loan or override Legal, Risk, or Compliance findings.
- Add deterministic unit tests for formula edge cases, missing data, zero denominators, and currency/period mismatches.
