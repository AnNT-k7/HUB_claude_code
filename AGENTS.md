# Income Verification Expert — Repository Instructions

Apply `$income-verification-dev` to all work in this repository.

For component-specific work, also apply the narrowest matching skill:

- `$income-document-extraction` — document classification, OCR/parsing, structured facts, and evidence.
- `$income-analysis` — salary transactions, deterministic calculations, anomalies, and consistency rules.
- `$income-policy-rag` — policy ingestion, embeddings, scoped retrieval, and citations.
- `$income-workflow` — Orchestrator, typed Case Context, state machine, consistency, and recommendations.
- `$income-action-executor` — human review, action permissions, idempotency, and mock integrations.

Use multiple component skills only when a task genuinely crosses boundaries.

## Source of truth

Read relevant documents in this order:

1. `docs/PRD.md`
2. `docs/PROJECT-RULES.md`
3. `docs/ARCHITECTURE.md`
4. `docs/RAG-ARCHITECTURE.md`
5. `docs/WORKFLOW.md`
6. `docs/PHASES.md`

Docs 2.x define the original target architecture from the design phase.
**`docs/architecture-current.md`, `docs/data-model.md`, `docs/agent-contracts.md`,
`docs/api.md`, `docs/rag-policy.md`, `docs/test-cases.md` and `docs/demo-script.md`
describe what is actually implemented today** (multi-case management, real
LLM/RAG via `app/services/llm_provider.py`, 20 synthetic ground-truth
cases) — read those alongside docs 2.x, and prefer them where the two
disagree on current state; docs 2.x remain the reference for target
architecture and guardrails. Existing department agents, Reviewer/Debate
flow, DSCR/LTV tools, and credit-contract operations are legacy code
(`app/legacy/`) until migrated; do not treat their presence as current scope.

## Guardrails

- Keep one actor: the unsecured-loan underwriter.
- Keep one task: verify customer income from the loan dossier.
- Never approve/reject a loan, set a limit, generate a credit contract, or disburse.
- Treat missing/unreadable evidence as incomplete/manual review; never infer facts.
- Use deterministic tools for arithmetic and numeric routing.
- Require exact policy citations and case-scoped customer evidence.
- Keep PII out of the global policy index and long-term LLM memory.
- Require human approval for official/outbound writes.
- Route mutations through the rule-based Action Executor using mock adapters only.
- Audit workflow, tool, policy, review, and action events without secrets or unmasked PII.

## Change discipline

Work in the active roadmap phase, migrate the smallest coherent slice, add deterministic tests, run focused checks, and report remaining legacy dependencies or stubs.
