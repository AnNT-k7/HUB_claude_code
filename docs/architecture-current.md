# Architecture (implementation-accurate, this pass)

> This document describes what the code actually does today. `docs/ARCHITECTURE.md`
> (pre-existing) describes the original target architecture from the design
> phase — treat it as historical intent, this file as current fact. (Named
> `architecture-current.md`, not `architecture.md`, because macOS's default
> case-insensitive filesystem would otherwise collide with `ARCHITECTURE.md`.)

## Component map

```
frontend/                          Static UI: case list, create case, case detail
  app.js                           Hash router (#/cases, #/cases/new, #/cases/:id)

backend/app/
├── api/v1/
│   ├── cases.py                   Multi-case API (primary path)
│   ├── income_verifications.py    Original fixed-demo API (backward compat)
│   ├── case_schemas.py            Request/response models for cases.py
│   └── schemas.py                 Shared models (Review, Evidence, Audit)
│
├── agents/income_verification/
│   ├── orchestrator.py            LangGraph StateGraph — routing/retry/checkpoint only
│   ├── state.py                   CaseContext + every typed contract
│   ├── document_agent.py          MarkdownDocumentAgent (fixed-demo fixture, regex)
│   ├── general_document_agent.py  GeneralDocumentAgent (uploaded cases, LLM+regex)
│   ├── income_agent.py            Deterministic salary classification + calculator calls
│   ├── policy_agent.py            RAG retrieval + LLM param extraction + eligible-income calc
│   ├── consistency_agent.py       Wraps app/tools/consistency_rules.py
│   ├── recommendation_builder.py  Assembles the final Recommendation
│   └── human_review.py            Review-outcome state machine
│
├── services/
│   ├── llm_provider.py            LLMClient abstraction (FPT/OpenAI/Anthropic/Mock)
│   ├── document_processing.py     Loader → TextExtractor → Classifier → FieldExtractor → EvidenceLocator
│   ├── case_service.py            Multi-case orchestration (CRUD, upload, run, review)
│   ├── case_document_store.py     Disk-backed per-case file storage
│   ├── runtime.py                 Original fixed-demo runtime (still wired, backward compat)
│   ├── namespace_rag.py           Embedding-based retrieval over the 3-namespace corpus
│   ├── embeddings.py              FPT/GLM/local embedding adapters
│   ├── action_executor.py         Rule-based, idempotent, mock LOS/DMS/Workflow/Notification
│   └── integrations/              Mock adapter implementations
│
├── tools/
│   ├── income_calculator.py       Deterministic Decimal arithmetic (average/variance/eligibility)
│   ├── consistency_rules.py       Deterministic finding rules (mismatch/anomaly/missing-doc)
│   └── routing_rules.py           Finding-severity → workflow-routing decision
│
├── db/
│   ├── case_models.py             Portable SQLAlchemy models (iv_cases/iv_documents/iv_audit_logs)
│   ├── case_session.py            SQLite-by-default engine/session for case_models
│   ├── models.py                  Postgres/pgvector-native models (target production path)
│   └── session.py                 Postgres session factory (models.py's, not case_models.py's)
│
└── legacy/                        Confirmed-unreferenced modules kept for reference only
```

## Two runtimes, one set of agents

There are two entry points into the same agent set, both real, both wired
to real RAG/LLM:

1. **`app/services/runtime.py` → `IncomeVerificationRuntime`** — the
   original fixed-demo path. `POST /api/v1/applications/SYN-SHB-2026-0001/income-verification`
   always operates on the one seeded synthetic case, using
   `MarkdownDocumentAgent` (regex over a fixture file — deliberately kept
   unchanged so the polished original demo case stays stable) but a real
   `PolicyAgent` with LLM-assisted parameter extraction and real RAG.

2. **`app/services/case_service.py` → `CaseService`** — the primary,
   general path. `POST /api/v1/cases` creates a case with a fresh
   `case_id`/`application_id`; documents are uploaded via
   `POST /cases/{id}/documents` and stored on disk
   (`app/services/case_document_store.py`) with metadata in SQLite;
   `POST /cases/{id}/run` runs the same `IncomeVerificationOrchestrator`
   (same LangGraph, same `WorkflowState` enum, same node functions) but with
   `GeneralDocumentAgent` — which reads whatever was actually uploaded, runs
   it through the LLM/regex extraction pipeline, and only ever accepts a
   fact if a Python check finds its claimed source quote verbatim in the
   extracted document text.

Both runtimes build their `PolicyAgent` via the same provider-selection
function (`_select_policy_retriever`): if an embedding API key is
configured, use `NamespacePolicyRetriever` (real cosine-similarity search);
otherwise fall back to `EmbeddedDemoPolicyRetriever` (a static metadata
filter) and label the case's `rag_mode` as `DEGRADED_KEYWORD_MATCH` so it's
visible, not silently swapped.

## The "LLM proposes, Python disposes" pattern

This is the one rule every LLM call site in this codebase follows, and it's
why the system can claim zero-hallucination arithmetic despite using an LLM
extensively:

1. The LLM is asked to extract a value **and** a verbatim quote containing
   it, from the actual source text.
2. A Python function checks the quote is a real (whitespace-normalized)
   substring of the source, and that the claimed value's digits appear in
   that quote (or, for table rows, in the same source line as the quote —
   see `_digits_appear_in_source_line` in `document_processing.py`, which
   handles the common case where a model quotes one cell of a multi-column
   row).
3. If validation fails, the value is dropped and a deterministic regex
   fallback is tried instead (`extract_fields_with_regex`,
   `_parse_integer_rule_value`).
4. All downstream arithmetic (`income_calculator.py`,
   `consistency_rules.py`) operates only on values that passed this gate —
   the LLM never computes an average, a variance, or an eligible-income
   figure itself.

This same pattern is used in three places: Document Agent field extraction,
Document Agent classification (keyword fallback instead of quote-check,
since classification isn't a quoted fact), and Policy Agent parameter
extraction (`_extract_policy_parameters` in `policy_agent.py`).

## Case lifecycle (WorkflowState)

Unchanged from the original design — see `app/agents/income_verification/state.py`'s
`CaseContext.ALLOWED_TRANSITIONS` for the authoritative state machine:

```
OPEN_CASE → FETCHING_DOCUMENTS → EXTRACTING_DOCUMENT_DATA
   → ANALYZING_INCOME_AND_POLICY → CROSS_CHECKING → BUILDING_RECOMMENDATION
   → HUMAN_REVIEW → EXECUTING_APPROVED_ACTIONS → VERIFYING_EXECUTION → COMPLETED

  (exception branches)
  FETCHING_DOCUMENTS → AWAITING_DOCUMENTS → FETCHING_DOCUMENTS (once supplemented)
  any analysis step  → MANUAL_REVIEW_REQUIRED
  EXECUTING_APPROVED_ACTIONS → TECHNICAL_ERROR → EXECUTING_APPROVED_ACTIONS (bounded retry)
```

`CaseService.run_pipeline()` for a brand-new case explicitly transitions
`OPEN_CASE → FETCHING_DOCUMENTS` and persists that before invoking the
orchestrator — this exists because the checkpoint store's optimistic-locking
invariant expects `state_version == 0` for a case with no prior saved row;
see the comment in `case_service.py::run_pipeline` for why this differs from
`runtime.py`'s simpler (single, pre-seeded case) flow.
