# Data model

## Persistence split

This codebase persists data in two independent SQLAlchemy model sets —
deliberately, not by accident (see `docs/architecture-current.md` for why
there are two runtimes):

- **`app/db/case_models.py`** (`CaseBase`) — the multi-case runtime's tables.
  Portable types only (`String`, `Integer`, `DateTime`, `JSON`) so SQLite
  (the default) and Postgres both work unmodified. Engine/session in
  `app/db/case_session.py`, driven by `Settings.case_database_url`
  (default `sqlite:///./data/case_management.db`).
- **`app/db/models.py`** (`Base`) — the original Postgres/pgvector-native
  target-production schema (`pgvector.Vector`, JSONB, native UUID). Not
  required to run this MVP; `VerificationCheckpoint` here is what
  `SqlAlchemyCheckpointStore` in `orchestrator.py` would use if wired to
  Postgres instead of the in-memory/SQLite stores actually used today.

## Case-management tables (`iv_*`, SQLite by default)

### `iv_cases`

| Column | Type | Notes |
| --- | --- | --- |
| `case_id` | `String` PK | e.g. `IV-A69837BA5C` |
| `application_id` | `String` unique | e.g. `APP-5E56746F` |
| `customer_name`, `customer_code`, `employer` | `String?` | Denormalized from `ExtractedFields` once extraction succeeds, or from create-case input |
| `requested_amount` | `String?` | Stored as string (not `Numeric`) to keep exact `Decimal` precision without a DB-specific numeric type |
| `loan_term_months` | `Integer?` | |
| `workflow_state` | `String` | Mirror of `CaseContext.workflow_state` |
| `verification_status` | `String?` | Mirror of `CaseContext.recommendation.status` once a recommendation exists |
| `state_version` | `Integer` | Optimistic-locking version (see `SqlCaseCheckpointStore`) |
| `context_payload` | `JSON` | **The full serialized `CaseContext`** — source of truth for the pipeline. Every other column here is a denormalized read model for the case-list query, rebuilt from this on each save. |

### `iv_documents`

One row per uploaded file: `document_id` (PK), `case_id` (FK), `file_name`,
`content_type`, `document_type` (classification result, nullable until the
pipeline runs or a user hint is given), `classification_method`
(`LLM` / `KEYWORD_FALLBACK` / `USER_HINT`), `checksum` (`sha256:...`),
`size_bytes`, `storage_path` (disk path under
`backend/data/case_documents/{case_id}/`), `parse_status`, `uploaded_at`.

### `iv_audit_logs`

Queryable mirror of `CaseContext.audit_events`: `case_id`, `event_id`,
`event_type`, `actor_type`, `actor_id`, `details` (JSON), `created_at`.
Rewritten (delete + reinsert) from the checkpoint on every save — simple and
correct at this data scale rather than incrementally appended.

## The `CaseContext` typed contract (`app/agents/income_verification/state.py`)

This is the actual shared state every agent reads/writes, and what
`context_payload` above serializes. Selected models (all Pydantic v2,
`extra="forbid"`):

```
CaseContext
├── case_id, application_id, task_type, workflow_state, state_version
├── documents: list[DocumentRecord]            # populated by fetch_documents()
├── extracted_fields: ExtractedFields | None    # Document Agent output
│     ├── customer_name, declared_income, contract_salary, currency,
│     │   employer, contract_expiry, extraction_confidence
│     ├── salary_transactions: list[SalaryTransaction]
│     └── variable_income_records: list[VariableIncomeRecord]
├── income_analysis: IncomeAnalysisResult | None  # Income Agent output
│     ├── average_income, variation_ratio, period_count
│     └── anomalies: list[IncomeAnomaly]
├── policy_result: PolicyResult | None            # Policy Agent output
│     ├── eligible_income, applied_rule_ids, citations: list[PolicyCitation]
│     └── parameter_extraction_method: str | None  # "LLM_VALIDATED" | "REGEX_FALLBACK"
├── findings: list[Finding]                       # Consistency Agent output
├── evidence: list[EvidenceCitation]               # every fact's source quote/page
├── recommendation: Recommendation | None
├── proposed_actions: list[ProposedAction]
├── human_review: HumanReviewRecord | None
├── execution_results: list[ExecutionResult]
├── errors: list[WorkflowError]
└── audit_events: list[AuditEvent]                 # append-only
```

Every `EvidenceCitation` carries `document_id`, `page_number`, `quote`, and
`source_checksum` — this is what makes a fact traceable back to its source,
and what the anti-hallucination validator in `document_processing.py`
checks against before a Document Agent-extracted fact is accepted.

## Known limitations in the data model / rule coverage

Documented here rather than silently absent, per the "không được giả vờ tích
hợp thành công một công nghệ chưa được triển khai" instruction this pass was
built under:

1. **`ExtractedFields.contract_expiry` is captured but not enforced.**
   `app/tools/consistency_rules.py::evaluate_consistency()` never compares
   it against the verification date, even though the policy corpus (IVP-5)
   requires ≥6 months remaining. See `docs/rag-policy.md` and the ground
   truth for synthetic cases 4–5 (`case_04_expired_contract`,
   `case_05_contract_expiring_soon`), which explicitly document this as an
   open gap rather than asserting behavior that doesn't exist.
2. **No `SecondaryIncomeRecord` type exists.** IVP-10 (secondary income
   sources should be noted but not auto-summed) is policy text only; there
   is no structured field or finding code for it yet
   (`case_10_multiple_income_sources`'s ground truth documents this).
3. **`extraction_confidence` is a computed, auditable heuristic, not an LLM
   self-report.** `document_processing.py::_compute_confidence()` derives it
   from the mix of `LLM_VALIDATED` / `REGEX_FALLBACK` / `NOT_FOUND` methods
   across the extracted fields — see IVP-14's `<0.90` threshold in the
   policy corpus, which is not yet wired into an actual routing check
   (the threshold exists as policy text; the gate that would compare a
   real case's confidence against it and force `MANUAL_REVIEW_REQUIRED`
   is not implemented).
