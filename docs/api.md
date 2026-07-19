# API reference

Base path: `/api/v1`. Every endpoint requires the demo auth headers:

```http
X-Role: UNDERWRITER
X-Reviewer-Id: <any non-empty string>
```

(`app/api/v1/income_verifications.py::require_underwriter` — a header-based
stand-in documented as needing to be replaced by real IAM before production,
unchanged from the original design.)

## Case management (`app/api/v1/cases.py`) — primary path

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/cases` | Create a case. Body: `{customer_name?, customer_code?, employer?, requested_amount?, loan_term_months?}`. Returns `{case_id, application_id, workflow_state: "OPEN_CASE"}`, `201`. |
| `GET` | `/cases` | List all cases (`CaseSummaryResponse[]` — denormalized, cheap; no `context_payload` deserialization). |
| `GET` | `/cases/system/status` | `{llm_mode, rag_mode}` — e.g. `"FPT:SaoLa3.1-medium (live)"` / `"EMBEDDING_RAG"`, or `"MOCK (...)"` / `"DEGRADED_KEYWORD_MATCH"`. Registered before `/{case_id}` so `"system"` is never captured as a case_id. |
| `GET` | `/cases/{case_id}` | Full `CaseContext` (extracted fields, income/policy results, findings, evidence, recommendation, actions, audit). |
| `GET` | `/cases/{case_id}/status` | Lightweight `{case_id, workflow_state, state_version, updated_at}` for polling. |
| `POST` | `/cases/{case_id}/documents` | Multipart upload: `file` (required), `document_type_hint` (optional form field). Returns the stored `DocumentSummaryResponse`. `422` on unsupported format/empty/oversize (>25MB). |
| `GET` | `/cases/{case_id}/documents` | List uploaded documents with classification metadata. |
| `GET` | `/cases/{case_id}/documents/{document_id}/download` | Raw file bytes, `Content-Disposition: inline`. |
| `POST` | `/cases/{case_id}/run` | Runs the orchestrator synchronously (blocks until a terminal/human-gate state — real LLM/RAG calls, typically 10–40s). Returns the updated `CaseContext`. |
| `POST` | `/cases/{case_id}/review` | Body matches `HumanReviewCommand`: `{outcome: ACCEPT_ACTIONS\|EDIT_AND_RERUN\|MANUAL_HANDLING, reason, approved_action_ids?, edited_eligible_income?}`. `409` on an invalid state transition (e.g. reviewing twice). |
| `POST` | `/cases/{case_id}/retry-actions` | Re-attempt a previously failed action execution. |
| `GET` | `/cases/{case_id}/evidence` | Just the `evidence` list (citations). |
| `GET` | `/cases/{case_id}/audit` | Just the `audit_events` list (append-only). |

All `404` on unknown `case_id` (`CaseNotFoundError`).

## Original fixed-demo API (`app/api/v1/income_verifications.py`) — backward compat

Identical shapes, but every path is pinned to the one seeded case
(`SYN-SHB-2026-0001` / `SYN-IV-001`):

| Method | Path |
| --- | --- |
| `POST` | `/applications/{application_id}/income-verification` (only `SYN-SHB-2026-0001` accepted, `422` otherwise) |
| `POST` | `/applications/{application_id}/income-verification/reset` (demo-only: forget the checkpoint) |
| `GET` | `/income-verifications/{case_id}` |
| `POST` | `/income-verifications/{case_id}/review` |
| `POST` | `/income-verifications/{case_id}/retry-actions` |
| `GET` | `/income-verifications/{case_id}/evidence` |
| `GET` | `/income-verifications/{case_id}/audit` |

## Example: full flow via curl

```bash
BASE=http://localhost:8000/api/v1
H=(-H "X-Role: UNDERWRITER" -H "X-Reviewer-Id: LT-01")

# 1. Create a case
CASE=$(curl -s "${H[@]}" -H "Content-Type: application/json" -X POST "$BASE/cases" \
  -d '{"customer_name":"Nguyễn Văn A","employer":"Công ty ABC","requested_amount":150000000,"loan_term_months":18}')
CASE_ID=$(echo "$CASE" | python3 -c "import json,sys;print(json.load(sys.stdin)['case_id'])")

# 2. Upload documents (repeat per file)
curl -s "${H[@]}" -F "file=@loan_application.txt" "$BASE/cases/$CASE_ID/documents"
curl -s "${H[@]}" -F "file=@employment_contract.txt" "$BASE/cases/$CASE_ID/documents"
curl -s "${H[@]}" -F "file=@bank_statement.txt" "$BASE/cases/$CASE_ID/documents"
curl -s "${H[@]}" -F "file=@payslip.txt" "$BASE/cases/$CASE_ID/documents"

# 3. Run the pipeline (real LLM/RAG calls — expect 10-40s)
curl -s "${H[@]}" -X POST "$BASE/cases/$CASE_ID/run"

# 4. Approve (collect approved_action_ids from the /run response's proposed_actions)
curl -s "${H[@]}" -H "Content-Type: application/json" -X POST "$BASE/cases/$CASE_ID/review" \
  -d '{"outcome":"ACCEPT_ACTIONS","reason":"Reviewed evidence.","approved_action_ids":["<id1>","<id2>"]}'
```

## Error handling

- `403` — missing/invalid `X-Role`/`X-Reviewer-Id`.
- `404` — unknown `case_id` / `document_id`.
- `409` — invalid human-review state transition (e.g. reviewing a case not
  in `HUMAN_REVIEW`, or reviewing twice).
- `422` — request validation failure (Pydantic — missing required field,
  wrong type) or unsupported/empty/oversize document upload.
- The pipeline itself never crashes the request on an LLM/RAG failure — see
  `docs/architecture-current.md`'s "LLM proposes, Python disposes" section:
  a failed LLM call falls back to a deterministic path, and a genuinely
  unresolvable case routes to `AWAITING_DOCUMENTS` or
  `MANUAL_REVIEW_REQUIRED` rather than returning a 5xx.
