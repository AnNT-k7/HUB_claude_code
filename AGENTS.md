# Digital Expert Agents — Repository Instructions

Apply `$digital-expert-agents-dev` to work in this repository.

For department-specific work, also apply the matching skill under `.codex/skills/departments/`:

- `$dea-customer-relationship`
- `$dea-credit`
- `$dea-risk-management`
- `$dea-legal-compliance`
- `$dea-collateral-appraisal`
- `$dea-banking-operations`

## Source of truth

- Read `docs/PRD.md` for product scope.
- Read `docs/PROJECT-RULES.md` for mandatory safety and architecture rules.
- Read `docs/ARCHITECTURE.md` for component boundaries and data flow.
- Read `docs/RAG-ARCHITECTURE.md` for chunking, filtering, and citation rules.
- Read `docs/PHASES.md` before selecting implementation work.
- Read `docs/WORKFLOW.md` for runtime state transitions and department handoffs.

## Guardrails

- Do not add features outside the MVP without explicit approval.
- Do not expose or commit secrets; keep local values in `.env` and use `.env.example` for placeholders.
- Never allow autonomous loan approval/rejection or production core-banking writes.
- Treat missing evidence as manual review; do not guess financial or legal facts.
- Keep customer data isolated by `case_id` and out of long-term policy embeddings.
- Use typed Shared Board state for agent communication and deterministic tools for financial ratios.
- Add audit traces for agent execution, board updates, debates, and operations.

## Change discipline

Keep changes within the active roadmap phase and layer. Run focused checks proportional to the change and report any remaining stubs or blockers.
