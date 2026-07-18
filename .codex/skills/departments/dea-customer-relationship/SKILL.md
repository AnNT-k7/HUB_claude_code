---
name: dea-customer-relationship
description: Develop or review the Customer Relationship Agent for borrower profiles, loan purpose, requested terms, and business context. Use when changing customer_relationship.py, its prompts/tools, or its Shared Board contract.
---

# Customer Relationship Agent

## Role

Extract and normalize the borrower profile, loan request, business model, key customers/suppliers, and stated repayment purpose from case evidence. This agent provides context for other specialists; it does not approve credit.

## Code contract

- Primary module: `backend/app/agents/tier2_board/specialists/customer_relationship.py`.
- Preserve `CustomerRelationshipAssessment` fields: `borrower_profile`, `requested_terms`, `business_model_summary`, `risk_flags`, and `evidence`.
- Post results to the typed Shared Board; never message another specialist directly.

## Evidence and RAG

- Use `CASE_EVIDENCE` for uploaded case documents and `POLICY_RULE` only for applicable customer/loan rules.
- Keep source document, page, section, and quote in every evidence item.
- If identity, purpose, or requested terms are missing or contradictory, return an incomplete/manual-review result and name the missing document.

## Guardrails

- Do not infer revenue, ownership, repayment capacity, or beneficial ownership.
- Do not turn a narrative profile into a credit decision.
- Isolate all case evidence by `case_id`; never index customer PII as long-term policy knowledge.
- Write deterministic extraction/normalization tests with synthetic cases.
