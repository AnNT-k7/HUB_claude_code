---
name: dea-banking-operations
description: Develop or review the Banking Operations Agent for human-approved status changes, mock SHB prechecks, draft agreement/onboarding outputs, and immutable audit traces. Use when changing operations.py or mock API clients.
---

# Banking Operations Agent

## Activation gate

Run only after an explicit human verification decision from the approval workflow. Pre-checks may be read-only; production banking mutations are never allowed.

## Code contract

- Primary module: `backend/app/agents/tier3_operations/operations.py`.
- Preserve `OperationsExecutionResult` fields: status, generated agreement URL, onboarding payload, mock API responses, and audit trace ID.
- Mock clients belong under `backend/app/mock_apis`; all actions must be auditable in `audit_logs`.

## Allowed actions

- Update the approved case state only through the controlled API workflow.
- Create missing-document requests when explicitly requested.
- Run read-only Mock SHB prechecks.
- Generate draft credit-agreement and onboarding JSON artifacts.
- Record complete request/response payload traces without secrets or unnecessary customer data.

## Guardrails

- Reject execution when human approval, case identity, required documents, or preconditions are missing.
- Never call production core-banking endpoints, disburse funds, or silently change a decision.
- Keep operations idempotent and test deterministic `200 OK` and `400 Bad Request` mock responses.
- Do not log API keys, passwords, tokens, or raw sensitive data beyond the minimum audit requirement.
