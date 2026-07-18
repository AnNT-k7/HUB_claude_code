---
name: digital-expert-agents-dev
description: Develop and review the Digital Expert Agents repository with its banking MVP scope, FastAPI/Next.js boundaries, LangGraph Shared Board, RAG citation rules, human approval gates, and audit requirements. Use for changes under HUB_claude_code, especially backend agents, RAG/storage, APIs, frontend assessment flows, tests, and architecture reviews.
---

# Digital Expert Agents Development

Use this skill as the project-level engineering contract. Keep the implementation aligned with the existing documents and prefer the smallest change that advances the current roadmap phase.

## Required context

Before changing code, read only the documents relevant to the task, in this order:

1. `docs/PRD.md` — MVP scope and user flow.
2. `docs/PROJECT-RULES.md` — non-negotiable safety, data, and architecture rules.
3. `docs/ARCHITECTURE.md` — components, state flow, and storage model.
4. `docs/RAG-ARCHITECTURE.md` — chunk taxonomy, filtering, citations, and zero-hallucination rules.
5. `docs/PHASES.md` — identify the active implementation phase.
6. `docs/WORKFLOW.md` — runtime state transitions and development workflow.

Treat `docs/` as the source of truth. If code and docs disagree, report the mismatch before making a broad architectural change.

## Workflow

1. Identify the affected layer: frontend, API, orchestration/agents, RAG/tools, storage, or mock APIs.
2. Identify the roadmap phase and keep the diff within that phase unless the user explicitly expands scope.
3. Preserve strict layer separation and typed contracts.
4. Implement deterministic calculations and validation before LLM calls.
5. Add or update deterministic tests for calculations, schemas, filters, and state transitions.
6. Run the narrowest relevant checks, then report changed files, verification, and remaining blockers.

## Department skill routing

Use the narrowest department skill when the task is specific to one agent:

- `$dea-customer-relationship` → `customer_relationship.py`
- `$dea-credit` → `credit.py` and financial calculation tools
- `$dea-risk-management` → `risk_management.py`
- `$dea-legal-compliance` → `legal.py`, `compliance.py`, and KYC/AML checks
- `$dea-collateral-appraisal` → `collateral_appraisal.py` and LTV tools
- `$dea-banking-operations` → Tier 3 operations and Mock SHB clients

For cross-department changes, invoke this project skill first and then apply every affected department contract.

## Non-negotiable invariants

- The system assists human officers; it never autonomously approves or rejects a loan.
- Operations and official status changes require explicit human verification and use Mock SHB APIs only.
- Missing or unreadable evidence produces an incomplete/manual-review result, never an inferred value.
- Policy conclusions require exact RAG citations with document, page, and section metadata.
- Customer documents and financial facts stay isolated by `case_id`; do not put customer PII in long-term policy embeddings.
- Specialist agents communicate through the typed Shared Board, not ad-hoc direct messages.
- DSCR, D/E, LTV, and similar metrics are calculated by deterministic tools from structured facts.
- Agent turns, board updates, debate rounds, and operational calls require audit traces.
- Never print, commit, or place API keys in source, documentation, fixtures, or logs. Use `.env` locally.

## Implementation guidance

- Backend routes belong in `backend/app/api`; business services in `backend/app/services`; persistence in `backend/app/db`; agent graphs in `backend/app/agents`.
- Keep specialist output Pydantic models explicit and status-driven (`PENDING`, success, incomplete/manual review, or error).
- Keep RAG department and `chunk_type` filters mandatory; do not perform unrestricted vector searches.
- Treat reviewer debate as a bounded quality loop with a configurable maximum round count.
- Keep frontend components focused on presentation and API state; do not duplicate backend policy logic in TypeScript.

## Quality checks

Use the installed security skills for threat modeling or security review, Playwright for browser flows, and GitHub skills for CI/PR work. For ordinary changes, prefer:

- `docker compose config` for compose validation.
- `npm run typecheck` and `npm run build` from `frontend` when frontend code changes.
- `python -m compileall backend/app` and focused deterministic tests when backend code changes.

Do not claim end-to-end readiness while routers, agent runners, RAG, storage, or tests remain stubs.
