# Legacy code

Modules moved here are unreferenced by the live application (confirmed by
repo-wide grep before moving). Kept for reference only — do not import from
`app/legacy/` in new code.

- `financial_calculator.py` — DSCR/D-E/LTV corporate-loan ratios. Out of scope
  per `docs/PROJECT-RULES.md` ("Ngoài phạm vi"); belonged to an earlier
  multi-department "Digital Expert Agents" concept, not the Income
  Verification Expert.
- `mock_shb_api.py` — a `MockSHBClient` simulating core-banking lookups from
  the same earlier concept; superseded by `app/services/integrations/`.
- `audit.py` — an in-memory `MOCK_AUDIT_LOGS` dict; superseded by the typed
  `CaseContext.audit_events` model in
  `app/agents/income_verification/state.py`, which is what
  `GET /income-verifications/{case_id}/audit` actually serves.
- `mock_endpoints.py` — empty placeholder file.
