---
name: dea-legal-compliance
description: Develop or review Legal and Compliance analysis for corporate governance, ownership, KYC, AML, sanctions, litigation, and regulatory evidence. Use when changing legal.py, compliance.py, or their shared review contracts.
---

# Legal & Compliance Agent

## Role

Check legal identity and governance, collateral title evidence, litigation/encumbrances, KYC, AML, sanctions, and regulatory concerns. Treat Legal and Compliance as one business department while preserving separate code outputs where useful.

## Code contract

- Legal module: `backend/app/agents/tier2_board/specialists/legal.py`.
- Compliance module: `backend/app/agents/tier2_board/specialists/compliance.py`.
- Preserve `LegalAssessment` and `ComplianceAssessment`; merge their findings only through the Shared Board.

## Evidence and RAG

- Use `LEGAL` or `COMPLIANCE` department tags consistently with indexed metadata; never search the full policy table without filters.
- Use `LEGAL_CLAUSE`, `POLICY_RULE`, and `CASE_EVIDENCE` chunks.
- Cite exact document, page, section, and quote for each legal or regulatory finding.
- If ownership, beneficial-owner, KYC, sanctions, or document validity is unclear, return manual review and identify the missing evidence.

## Guardrails

- Do not state that a document is legally valid beyond the evidence available.
- Do not replace sanctions/KYC checks with LLM judgment; use deterministic/mock checkers.
- Do not approve the loan or authorize disbursement.
- Test conflicting names, expired documents, high-risk matches, and unresolved litigation.
