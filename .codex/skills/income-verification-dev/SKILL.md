---
name: income-verification-dev
description: Develop and review the Income Verification Expert repository against its one-actor, one-task MVP, FastAPI/Next.js boundaries, typed Case Context, scoped policy RAG, deterministic income calculations, human review, Action Executor permissions, and audit rules. Use for any implementation, refactor, test, documentation, or architecture work under HUB_claude_code.
---

# Income Verification Expert Development

Use this skill as the repository-wide engineering contract. Treat the approved docs as target architecture and legacy department agents as migration inputs, not current scope.

## Required context

Read only what the task needs, in this order:

1. `docs/PRD.md` and `docs/PROJECT-RULES.md` for scope and invariants.
2. `docs/ARCHITECTURE.md` for component and data boundaries.
3. `docs/RAG-ARCHITECTURE.md` for policy ingestion/query work.
4. `docs/WORKFLOW.md` for state, orchestration, review, or action work.
5. `docs/PHASES.md` before selecting implementation work.

If code and docs 2.x disagree, report the mismatch and migrate the smallest coherent slice. Do not extend the legacy multi-department pipeline.

## Component routing

Apply the narrowest component skill in addition to this skill:

- `$income-document-extraction` for document parsing, OCR, structured facts, and evidence.
- `$income-analysis` for salary transaction classification, calculations, and consistency rules.
- `$income-policy-rag` for policy ingestion, embeddings, retrieval, and citations.
- `$income-workflow` for Orchestrator, Case Context, state machine, consistency, and recommendations.
- `$income-action-executor` for human review, action permissions, idempotency, and mock integrations.

Use multiple component skills only when the change genuinely crosses their boundaries.

## Workflow

1. Identify the active roadmap phase and affected component.
2. Compare current code with the target paths/contracts in `ARCHITECTURE.md`.
3. Preserve typed layer boundaries and case isolation.
4. Put arithmetic and routing in deterministic tools before LLM calls.
5. Add tests for schemas, calculations, filters, state transitions, permissions, and failure paths.
6. Run focused checks and report remaining legacy dependencies or stubs.

## Non-negotiable invariants

- Support only the income-verification task for the unsecured-loan underwriter.
- Never approve/reject a loan, set a limit, generate a credit contract, or disburse.
- Treat missing/unreadable evidence as incomplete/manual review; never infer facts.
- Require source evidence for customer facts and exact citations for policy conclusions.
- Keep customer data scoped by `case_id`; never place PII in the global policy index.
- Let specialist components communicate only through typed `CaseContext` namespaces.
- Let deterministic tools calculate income metrics and apply routing thresholds.
- Require human approval for official/outbound writes.
- Route all mutations through the rule-based Action Executor and mock adapters.
- Audit agent/tool turns, state transitions, policy queries, reviews, and actions without logging secrets or unmasked PII.

## Layer boundaries

- `frontend/`: presentation and API state only.
- `backend/app/api/`: auth, request validation, response formatting.
- `backend/app/agents/income_verification/`: target agent workflow and state.
- `backend/app/tools/`: deterministic calculations and rules.
- `backend/app/services/`: RAG, storage, actions, and adapters.
- `backend/app/db/`: persistence and transactions.
- `backend/app/mock_apis/`: MVP integrations only.

## Quality checks

Choose checks proportional to the change:

- docs/skills: validation, stale-reference search, and `git diff --check`;
- backend: `python -m compileall backend/app` plus focused tests;
- frontend: typecheck/build plus browser flow tests when applicable;
- infrastructure: `docker compose config`;
- RAG: metadata/filter/citation/isolation tests;
- workflow/actions: transition, retry, permission, idempotency, and audit tests.

Do not claim end-to-end readiness while target modules or required tests remain absent.
