---
name: income-workflow
description: Implement or review the Income Verification Expert Orchestrator, typed Case Context, state machine, parallel specialist execution, consistency routing, recommendation building, retries, checkpoints, and audit transitions. Use for LangGraph/workflow code, agent state schemas, orchestration APIs, missing-data paths, and migration away from the legacy tiered department pipeline.
---

# Income Verification Workflow

Coordinate the approved income-verification state machine. Keep business arithmetic, policy invention, and system mutations outside the Orchestrator.

## Required context

Read:

1. `docs/ARCHITECTURE.md` sections 2, 3, 5, and 6.
2. `docs/WORKFLOW.md` completely.
3. `docs/PROJECT-RULES.md` sections 2, 3, 8, and 9.
4. `docs/PHASES.md` before migration work.

## Orchestrator contract

- Open/resume only `task_type=INCOME_VERIFICATION` workflows.
- Dispatch Document, Income, Policy, Consistency, and Recommendation components.
- Run Income and Policy branches in parallel after document facts are ready.
- Validate typed outputs, checkpoint state, apply deterministic routing, and bound technical retries.
- Never calculate income, interpret policy, decide a loan, or call mutation APIs.

## Case Context

Use one typed `CaseContext` with versioning and component-owned namespaces for documents, extracted facts, income analysis, policy results, findings, evidence, recommendation, proposed actions, human review, execution results, and errors.

Use optimistic locking or transactions. Keep evidence, audit, review, and execution history append-only.

## State machine

Use the exact states and transitions in `docs/WORKFLOW.md`. Do not introduce generic loan states such as `APPROVED` or `REJECTED`; `EXECUTING_APPROVED_ACTIONS` refers only to accepted verification actions.

Treat missing documents, unreadable evidence, policy not found/conflict, material mismatch, and exhausted retries as explicit non-success paths.

## Consistency and recommendation

- Let deterministic rules assign numeric severity and routing.
- Preserve facts, calculations, policy citations, and unresolved issues.
- Build a reviewable verification result and proposed actions, never a credit decision.
- Route edits only to affected steps when dependencies are known.

## Retry and audit

- Retry transient technical errors only, with timeout, max attempts, and backoff.
- Do not retry business exceptions to force an answer.
- Audit workflow open/resume, component turns, state updates, rules, reviews, and action results without secrets or unmasked PII.

## Testing

Cover happy path, parallel branch join, schema failure, missing documents, unreadable evidence, policy not found/conflict, material mismatch, edit/re-run, manual handling, bounded retry, checkpoint/resume, concurrent version conflict, and audit completeness.
