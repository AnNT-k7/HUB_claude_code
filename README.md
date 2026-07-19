# Digital Expert Agents — Income Verification (SHB)

A multi-agent AI system built for the **Vietnam AI Innovation Challenge 2026 /
Hack CX Together** challenge from **SHB Bank**: *"Digital expert agents"* — a
team of digital experts, each an agent specialized in one banking domain,
that plans, uses tools, retrieves internal knowledge (RAG) and takes real
action inside a bank's operating systems instead of only answering questions.

This submission implements the first fully working expert: **unsecured-loan
income verification**. One underwriter, one task — verify a customer's
declared income against their loan dossier, bank policy, and salary
transaction history — end to end, with a human always in the loop before
anything is written to a business system, and **any number of real cases**,
not one fixed demo record.

## What problem this solves

An underwriter verifying a personal loan applicant's income today reads,
by hand, a loan application, an employment contract (plus amendments), a
payslip bundle, and a bank statement — cross-checking names, employer, salary
figures, transfer sources, and statement coverage against internal policy.
It is slow and easy to get subtly wrong (an abbreviated employer name on a
statement, a contract about to expire, one anomalous month of income).

This system runs that cross-check for the underwriter: it classifies
uploaded documents, extracts income facts with every value traceable back to
a verbatim quote in the source text, computes eligible income with
deterministic arithmetic (never an LLM), retrieves the applicable policy
rules via a real vector-similarity search over an approved policy corpus,
flags mismatches/anomalies/missing documents, and produces an evidence-backed
recommendation — which the underwriter must still explicitly accept, edit, or
reject before anything is written anywhere. **It never scores credit,
approves a loan, or sets a limit.**

## What's genuinely real here (and what's still a documented gap)

This codebase went through a full pass specifically to close the gap between
"looks like an AI system" and "is one." Concretely:

| Claim | Status |
| --- | --- |
| LLM actually extracts/classifies documents | **Real.** `app/services/document_processing.py` calls the configured LLM (FPT AI Marketplace by default) for document classification and structured field extraction, with every LLM-proposed value validated against a verbatim quote from the source text before acceptance. |
| RAG actually retrieves policy by embedding similarity | **Real.** `app/agents/income_verification/policy_agent.py`'s `NamespacePolicyRetriever` runs real cosine-similarity search over a 512-dim FPT-embedded corpus (`backend/data/rag/three_rag_fpt_corpus.json`). Falls back to a labelled `DEGRADED_KEYWORD_MATCH` mode (never silently) if no embedding key is configured. |
| Arithmetic is deterministic, not LLM guesswork | **Real, unchanged from the original design.** `app/tools/income_calculator.py` and `app/tools/consistency_rules.py` do every average/variance/eligibility/mismatch calculation in typed Python; the LLM never touches a number without a Python-verified quote backing it. |
| Multiple cases, real upload, real persistence | **Real.** `POST /api/v1/cases` + multipart upload + SQLite (`backend/data/case_management.db`) — see "New in this pass" below. |
| Contract-expiry policy check (IVP-5, ≥6 months remaining) | **Documented gap.** The policy text exists in the corpus; `app/tools/consistency_rules.py` does not yet compare `contract_expiry` against the verification date. Flagged in `docs/data-model.md` and in the synthetic test-case ground truth (cases 4–5), not swept under the rug. |
| Secondary/multiple income source detection (IVP-10) | **Documented gap.** Policy text exists; no code path specifically detects/labels a second income source yet. |
| OCR for scanned images/PDFs | **Best-effort, optional.** Uses local `pytesseract` if installed; otherwise a document is marked `ocr_unavailable`/`UNREADABLE` rather than inventing text. No cloud OCR service is wired in. |
| Real SHB documents in `dataset/` | **Deliberately unused.** Only the synthetic markdown/notes corpus is ingested (`APPROVED_FOR_DEMO`); the real SHB PDFs sit quarantined by the ingestion scripts. The policy corpus itself says so in its own front-matter (`issuer: SYNTHETIC_SHB_DEMO`, `production_use: prohibited`). |

## New in this pass (upgrade from the original hard-coded demo)

The project originally shipped as a single hard-coded case (`SYN-IV-001` /
`SYN-SHB-2026-0001`) with document extraction reading one markdown fixture
via regex, and no LLM call anywhere in the executed pipeline. This pass adds:

1. **Multi-case management** — `POST /api/v1/cases` (create), document
   upload (`POST /cases/{id}/documents`), listing, run, status, review,
   evidence, audit, and document download, backed by SQLite
   (`app/db/case_models.py`, `app/services/case_service.py`). No endpoint is
   hard-wired to the old fixed case.
2. **A real LLM provider layer** (`app/services/llm_provider.py`) —
   `FPTLLMProvider` (default, matches the competition-issued key),
   `OpenAIProvider`/`AnthropicProvider` (optional, same shape), and
   `MockLLMProvider` (deterministic no-op, used automatically when no key is
   configured and explicitly in tests).
3. **A generalized Document Agent** (`app/services/document_processing.py`,
   `app/agents/income_verification/general_document_agent.py`) — Loader →
   TextExtractor (PDF text/CSV/plain text/best-effort OCR) → Classifier
   (LLM + keyword fallback) → FieldExtractor (LLM + regex fallback, every
   value quote-verified) → EvidenceLocator, replacing the fixture-only
   `MarkdownDocumentAgent` for uploaded cases (that agent still powers the
   original fixed demo case at `/applications/SYN-SHB-2026-0001/...`,
   untouched, for backward compatibility).
4. **Policy Agent LLM-assisted parameter extraction** — the three numeric
   policy parameters (required statement months, variable-income cap,
   minimum documented periods) are now extracted by the LLM from retrieved
   policy text with a Python verbatim-quote validator, falling back to the
   original regex parser if the LLM is unavailable or fails validation.
5. **Real RAG wired in everywhere** — both the new multi-case runtime and
   the original fixed-demo runtime now use `NamespacePolicyRetriever` (real
   embedding search) instead of the old `EmbeddedDemoPolicyRetriever`
   (hardcoded `score=1.0` metadata filter), with an explicit, audited
   fallback if no embedding key is present.
6. **An expanded policy corpus** — 15 rule groups (IVP-1…IVP-15) covering
   minimum employment duration, declared-vs-statement mismatch, employer-name
   verification, multiple income sources, cash salary, foreign currency,
   required-document lists, extraction-confidence thresholds, and a
   consolidated manual-review trigger list — re-embedded with the real FPT
   embedding API (`backend/data/rag/three_rag_fpt_corpus.json`).
7. **20 synthetic ground-truth test cases** (`backend/data/synthetic_cases/`,
   generated by `backend/scripts/generate_synthetic_cases.py`) covering
   missing documents, expired/expiring contracts, income mismatches in both
   directions, volatile income, bonuses, multiple income sources, foreign
   currency, cash salary, abbreviated/mismatched employer names, fake
   salary-like transactions, incomplete statements/payslips, and a compound
   multi-issue case — all runnable fully offline (`LLM_PROVIDER=mock`).
8. **A generalized frontend** — case list, create-case (with file upload),
   and a per-case detail view reachable at any `case_id` (hash-routed,
   `#/cases`, `#/cases/new`, `#/cases/:id`) instead of one hard-coded screen;
   a live LLM/RAG mode badge; document and audit-trail viewers wired to
   endpoints that existed in the API but were never called from the UI; and
   an honest waiting state during the real (now multi-second) LLM/RAG call
   instead of a fixed-`sleep()` animation that used to run regardless of
   actual backend timing.
9. **Dead code moved to `backend/app/legacy/`** (confirmed unreferenced by
   grep before moving: `financial_calculator.py`/DSCR-LTV tools out of
   scope, `mock_shb_api.py`, the unused in-memory `audit.py`) and stale
   manual test scripts referencing deleted modules moved to
   `backend/scripts/legacy/` — `pytest` now collects and passes cleanly from
   a clean checkout.

## Architecture

```
Underwriter UI (case list → create case → case detail)
      │
      ▼
Orchestrator Agent  (LangGraph state machine, retry/timeout, no domain logic)
      │ dispatch (parallel)
      ├──────────────┬──────────────┐
      ▼              ▼              ▼
Document Agent   Income Agent    Policy Agent
(LLM classify +  (deterministic  (RAG retrieval +
 LLM/regex        Decimal math)   LLM param extraction,
 extraction,                      quote-validated)
 quote-validated)
      └──────────────┴──────────────┘
                     ▼
            Consistency Agent  (deterministic rule engine)
                     ▼
         Recommendation Builder
                     ▼
          Human Review Gate  (approve / edit / reject — never auto-executed)
                     ▼
            Action Executor  (rule-based, idempotent, mock LOS/DMS/Workflow/Notification)
```

Every specialist agent is read/compute-only inside its task scope. Only the
Action Executor is allowed to call the (mocked) bank systems, and only after
a human decision. See `AGENTS.md`, `docs/PROJECT-RULES.md`, and
`docs/architecture-current.md` (this pass's implementation-accurate architecture doc)
for the full guardrails.

## What's in this repo

| Path | What it is |
| --- | --- |
| `backend/` | FastAPI + LangGraph multi-agent workflow, LLM provider layer, RAG, case-management API, SQLite persistence |
| `frontend/` | Dependency-free static app (case list, create case, case detail) wired to the live backend API |
| `dataset/` | Synthetic policy corpus, synthetic dossier fixture, real (unused) SHB PDFs kept for reference |
| `docs/` | `architecture.md`, `data-model.md`, `agent-contracts.md`, `api.md`, `rag-policy.md`, `test-cases.md`, `demo-script.md` (this pass) plus the original target-architecture design docs (`PRD.md`, `ARCHITECTURE.md`, `RAG-ARCHITECTURE.md`, `WORKFLOW.md`, `PHASES.md`, `PROJECT-RULES.md`) |

## Quickstart

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio  # test-only deps
uvicorn app.main:app --reload --port 8000
```

No PostgreSQL, MinIO or LLM API key is required to start the server — the
case-management database is SQLite by default (`backend/data/case_management.db`,
created automatically) and every LLM call falls back to a deterministic mock
if `LLM_PROVIDER=mock` or no provider key is configured. See
["Configuring the LLM"](#configuring-the-llm) below for wiring a real key.

### 2. Frontend

```bash
cd frontend
python3 -m http.server 8080
```

Open `http://localhost:8080`. It talks to `http://localhost:8000/api/v1` by
default (override with `localStorage.setItem('iv_api_base', '...')` in the
browser console, e.g. when tunnelling the backend for a demo).

### 3. Seed the 20 synthetic ground-truth cases (optional, for demo/testing)

```bash
cd backend
python3 scripts/generate_synthetic_cases.py     # writes backend/data/synthetic_cases/*
python3 scripts/seed_synthetic_cases.py --run   # creates + uploads + runs all 20 through the real API
```

### 4. Run the tests

```bash
cd backend
pytest tests/ -q
```

46 tests, all fast (~3s) and network-free — every LLM-touching test
dependency-injects `MockLLMProvider` + a keyword-match policy retriever
(`docs/PROJECT-RULES.md` §10: workflow tests must pass without a live LLM).

## Configuring the LLM

```env
LLM_PROVIDER=fpt              # fpt (default) | openai | anthropic | mock
LLM_MODEL=SaoLa3.1-medium     # any FPT AI Marketplace chat model; see below
FPT_API_KEY=...               # issued for this competition; also used for embeddings
```

FPT AI Marketplace is OpenAI-Chat-Completions-compatible and serves several
chat models behind one key (`SaoLa3.1-medium`, `DeepSeek-V4-Flash`,
`GLM-5.1`/`5.2`, `Qwen3.6-27B`, `Llama-3.3-70B-Instruct`, `gpt-oss-20b/120b`).
`SaoLa3.1-medium` is the default: it is FPT's own model, cheapest of the
models verified to return clean JSON in the response `content` field (some
reasoning-tuned models put output in `reasoning_content` instead — the
provider wrapper handles both), and appropriate for a Vietnamese-language
banking workload. Swap `LLM_MODEL` to try another.

Set `LLM_PROVIDER=mock` (or simply leave every provider key blank) to run
the entire pipeline deterministically with zero network calls — every LLM
call site has a Python-verified deterministic fallback (regex extraction,
keyword classification), so the pipeline still produces a correct result,
just without LLM-assisted polish. The frontend's mode badge and
`GET /api/v1/cases/system/status` always report which mode is active — the
UI never silently implies a live LLM/RAG integration that isn't there.

## Current limitations

- **Contract-expiry and secondary-income-source policy checks are not yet
  code-enforced** (see table above) — documented, not hidden.
- **OCR is local-only and optional** — no cloud OCR/vision service is wired
  in; scanned documents with no local `pytesseract` fall back to an explicit
  `UNREADABLE`/`ocr_unavailable` state rather than guessed text.
- **SQLite is the case-management default** — swap `CASE_DATABASE_URL` to a
  Postgres DSN to move the same schema there (the models use portable
  SQLAlchemy types precisely so this works); the separate
  Postgres/pgvector-native models in `app/db/models.py` remain the intended
  production path per `docs/ARCHITECTURE.md` and are not required for this
  MVP.
- **The original fixed-demo endpoints still exist** (`/applications/{id}/income-verification`)
  for backward compatibility and now also use real RAG/LLM, but they always
  operate on the one seeded synthetic case. The multi-case `/cases/*` API is
  the primary path.
- **Real SHB PDFs in `dataset/` are intentionally not ingested** — see the
  table above.

## Demo script

See `docs/demo-script.md` for a 3–5 minute walkthrough (create a case →
upload documents → run the pipeline → inspect evidence/audit → human
review → completed).
