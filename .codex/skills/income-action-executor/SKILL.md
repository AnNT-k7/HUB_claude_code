---
name: income-action-executor
description: Implement or review Human Review Gate outcomes, action permission classes, authorization, state preconditions, idempotency, mock LOS/DMS/Workflow/Notification adapters, execution verification, and audit for Income Verification Expert. Use for review APIs/UI, Action Executor services, outbound requests, official writes, internal tasks, and integration contract tests.
---

# Income Action Executor

Separate analysis from effects. Execute only typed actions allowed by policy and workflow state; require human approval for official or outbound changes.

## Required context

Read:

1. `docs/PROJECT-RULES.md` sections 6, 7, and 9.
2. `docs/ARCHITECTURE.md` sections 3.9, 3.10, 4, and 8.
3. `docs/WORKFLOW.md` sections 4.7, 4.8, and 6–8.

## Human review contract

Support explicit outcomes:

- accept verification actions;
- edit facts/actions with a reason and re-run affected steps;
- reject the AI result and continue manual handling.

These outcomes never approve or reject the loan. Persist reviewer identity, timestamp, edits, outcome, and reason. Do not reuse reviews as training data automatically.

## Permission classes

Allow automatic execution only for read-only or reversible internal work, such as authorized document fetch, draft generation, evidence attachment, internal task/label creation, and review-queue routing.

Require human approval for outbound missing-document requests, official eligible-income writes, official LOS notes, closing the verification step, or advancing the case.

Prohibit loan approval/rejection, limit changes, policy override, source-document mutation, disbursement, credit-contract generation, and production endpoints in MVP.

## Executor contract

For every action:

1. Validate the typed schema and allowed action type.
2. Authenticate the requester and verify reviewer authority when required.
3. Check case/workflow state preconditions.
4. Enforce permission class and human approval.
5. Reserve/check a stable idempotency key.
6. Call a typed mock adapter, never an agent-generated endpoint/payload.
7. Read back or otherwise verify the result.
8. Record masked audit data and return a structured execution result.

Never let an LLM invoke integrations directly.

## Failure handling

- Retry transient failures only with bounded backoff.
- Verify ambiguous responses before retrying.
- Keep failed/partial actions visible; never mark the workflow complete silently.
- Do not log secrets, raw documents, or unmasked PII.
- Preserve enough references and versions to reconstruct the action.

## Testing

Cover authorization, missing approval, invalid state, permission classes, prohibited actions, idempotent duplicates, adapter success/failure/timeout, ambiguous response verification, retry exhaustion, audit masking, and prevention of production endpoint use.
