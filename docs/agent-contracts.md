# Agent contracts

Every agent is a plain async callable matching one of two shapes used by
`app/agents/income_verification/orchestrator.py::WorkflowDependencies`:

```python
FetchDocuments  = Callable[[CaseContext], Awaitable[list[DocumentRecord]]]
ExtractDocuments = Callable[[CaseContext], Awaitable[DocumentExtractionResult]]
AnalyzeIncome   = Callable[[CaseContext], Awaitable[IncomeAnalysisResult]]
RetrievePolicy  = Callable[[CaseContext], Awaitable[PolicyResult]]
```

No agent calls another agent directly, no agent sends free-form prompts to
another agent, and no agent writes to a namespace it doesn't own in
`CaseContext` — they communicate only through the typed state object the
Orchestrator passes around. This is unchanged from the original design and
still enforced by construction (each function receives a deep copy of
`CaseContext`, mutates only its own output field, and returns).

## Document Agent

Two interchangeable implementations, both satisfying the same
`fetch_documents` / `__call__` contract:

- **`MarkdownDocumentAgent`** (`document_agent.py`) — regex-only, reads one
  fixed markdown fixture. Powers the original demo case only.
- **`GeneralDocumentAgent`** (`general_document_agent.py`) — reads whatever
  was uploaded for a `case_id` via an injected `DocumentIndex` (in
  production, `SqlDocumentIndex` in `case_service.py`, reading SQLite +
  disk). Pipeline per document: `load_document` → `extract_text` (PDF/CSV/
  plain text, best-effort OCR) → `classify_document` (LLM, falling back to
  keyword scoring) → consolidated `extract_fields_with_llm` across all
  documents → `extract_fields_with_regex` fallback → `merge_extractions`
  (LLM value if present and quote-validated, else regex value) →
  `build_extraction_result` (EvidenceLocator: locates each accepted value's
  page number by scanning the source document's pages for its quote).

  Returns `ComponentStatus.MISSING_DATA` (never a guess) if no documents are
  readable, or if core fields (`customer_name`, `declared_income`) are
  absent after both LLM and regex attempts.

## Income Analysis Agent (`income_agent.py`)

Purely deterministic — no LLM call. `select_recognized_transactions()`
classifies each `SalaryTransaction` as recognized/excluded using
`source_matches_employer()` (token-overlap matching after stripping
corporate-designation stopwords — see `docs/data-model.md`'s note on the
identical-but-separate matcher in `consistency_rules.py`). Recognized
transactions go to `app/tools/income_calculator.py::calculate_income_metrics()`
for average/variance/anomaly detection — Decimal arithmetic, never LLM math.

## Policy Agent (`policy_agent.py`)

1. Queries the `POLICY` namespace via the injected `PolicyRetriever`
   (`NamespacePolicyRetriever` = real embedding search, or
   `EmbeddedDemoPolicyRetriever` = degraded metadata-filter fallback) for
   the 6 required rule IDs (`IVP-1`..`IVP-6`), filtered by
   domain/product/effective-date/approval-status — see `docs/rag-policy.md`.
2. If any required rule is missing → `POLICY_NOT_FOUND`. If a rule ID has
   conflicting content across hits → `CONFLICT`. Never invents a rule.
3. Extracts three numeric parameters (statement months, variable-income
   cap, minimum documented periods) via `_extract_policy_parameters()` —
   LLM structured extraction with a verbatim-quote validator
   (`_quote_verbatim_and_contains_digits`), falling back to the original
   regex parser (`_parse_integer_rule_value`) if the LLM is unavailable or
   its answer fails validation. `PolicyResult.parameter_extraction_method`
   records which path was used, per case, for audit.
4. Computes `eligible_income` via `app/tools/income_calculator.py::calculate_eligible_income()`
   — deterministic Decimal math; the LLM only ever supplied the three input
   parameters, never touched this calculation.

## Consistency Agent (`consistency_agent.py` → `tools/consistency_rules.py`)

Purely deterministic rule engine — no LLM call in the current build (the
original architecture doc permits LLM-assisted finding *phrasing* here;
this pass did not wire that in — findings are template strings with
computed values interpolated, same as before). Checks implemented (exact
codes, see `docs/data-model.md` for what's *not* yet implemented):
`DECLARED_VS_AVERAGE_MISMATCH`, `DECLARED_VS_ELIGIBLE_MISMATCH`,
`CONTRACT_VS_AVERAGE_MISMATCH` (all via `_difference_ratio` against
configurable warning/critical thresholds), `CURRENCY_MISMATCH`,
`EMPLOYER_SOURCE_MISMATCH`, `INCOME_PERIOD_ANOMALY` (one per detected
anomaly), `MISSING_REQUIRED_DOCUMENT`, `INSUFFICIENT_STATEMENT_PERIOD`,
`POLICY_CITATION_MISSING`, `CALCULATION_LINEAGE_MISSING`,
`UNRESOLVED_EVIDENCE_REFERENCE`. Only `CRITICAL`-severity findings force
`MANUAL_REVIEW_REQUIRED` (`has_material_findings()`); `WARNING`-severity
findings still let the case reach `HUMAN_REVIEW`, surfaced for the
underwriter's judgment via `Recommendation.status = NEEDS_CLARIFICATION`.

## Recommendation Builder (`recommendation_builder.py`)

Assembles the final `Recommendation` from already-computed values — no
credit decision, no LLM. `summary` is a static compliance-framing string
(unchanged from the original design); the numeric fields
(`declared_income`, `average_income`, `eligible_income`) and `findings` are
copied through from upstream agent outputs.

## Human Review Gate (`human_review.py`)

Pure state-machine validation, no LLM. `apply_human_review()` enforces:
reviewer identity required; case must be in `HUMAN_REVIEW`; a
recommendation must exist; approved action IDs must exist and must not be
`ActionPermission.PROHIBITED`; `EDIT_AND_RERUN` requires an explicit edited
value and rewinds to `BUILDING_RECOMMENDATION`; `MANUAL_HANDLING` cannot
carry approved action IDs.

## Action Executor (`services/action_executor.py`)

Rule-based application service, **not an LLM agent** — this was true before
this pass and remains true. Validates schema, permission class
(`AUTO_REVERSIBLE` / `HUMAN_REQUIRED` — no `ActionType` currently maps to
`PROHIBITED`; the "cấm" category from the architecture doc is enforced by
the *absence* of any executable action for those cases, not by an active
rule — see `docs/data-model.md`), idempotency key, and calls a mock
integration adapter (`services/integrations/`).
