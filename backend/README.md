# Income Verification Expert — Backend

FastAPI + LangGraph multi-agent backend for the unsecured-loan income
verification workflow. One actor (the underwriter), one task (verify income
from the loan dossier) — see `AGENTS.md` and `docs/PROJECT-RULES.md` for the
guardrails this service is built around, and `../docs/architecture-current.md`
for what's actually implemented as of this pass (multi-case management, real
LLM/RAG, 20 synthetic ground-truth cases — the root `README.md` has the full
picture).

## Quickstart

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio  # test-only deps
uvicorn app.main:app --reload --port 8000
```

No Postgres, MinIO, or LLM API key is required to start: the case-management
database is SQLite by default (`data/case_management.db`, auto-created), and
every LLM call site falls back to a deterministic mock (`MockLLMProvider`)
when no provider key is configured. Set `FPT_API_KEY` + `LLM_PROVIDER=fpt`
in `.env` (see `../.env.example`) for real LLM-assisted extraction and real
RAG retrieval — see the root `README.md`'s "Configuring the LLM" section.

Open `http://localhost:8000/docs` for interactive OpenAPI docs. Full
endpoint reference: `../docs/api.md`.

## The primary API: multi-case management

```bash
BASE=http://localhost:8000/api/v1
H=(-H "X-Role: UNDERWRITER" -H "X-Reviewer-Id: LT-01")

curl -s "${H[@]}" -H "Content-Type: application/json" -X POST "$BASE/cases" \
  -d '{"customer_name":"Nguyễn Văn A","employer":"Công ty ABC"}'
# → {"case_id": "IV-...", "application_id": "APP-...", "workflow_state": "OPEN_CASE"}

curl -s "${H[@]}" -F "file=@loan_application.txt" "$BASE/cases/IV-.../documents"
curl -s "${H[@]}" -X POST "$BASE/cases/IV-.../run"
```

See `../docs/api.md` for the full endpoint table and `../docs/demo-script.md`
for a walkthrough. `../docs/test-cases.md` covers the 20 synthetic
ground-truth cases in `data/synthetic_cases/`.

## Exercising the original fixed-demo case (backward compat)

Every request needs a demo auth header pair:

```http
X-Role: UNDERWRITER
X-Reviewer-Id: LT-01
```

```bash
BASE=http://localhost:8000/api/v1
H=(-H "Content-Type: application/json" -H "X-Role: UNDERWRITER" -H "X-Reviewer-Id: LT-01")

# Run the full agent pipeline (Document → Income + Policy → Consistency → Recommendation)
curl -X POST "${H[@]}" -d '{}' "$BASE/applications/SYN-SHB-2026-0001/income-verification"

# Inspect the resulting case (extracted fields, findings, recommendation, audit trail)
curl "${H[@]}" "$BASE/income-verifications/SYN-IV-001"

# Human review: accept every proposed action and let the Action Executor run
curl -X POST "${H[@]}" -d '{
  "outcome": "ACCEPT_ACTIONS",
  "reason": "Reviewed evidence, approving system updates.",
  "approved_action_ids": ["<ids from proposed_actions>"]
}' "$BASE/income-verifications/SYN-IV-001/review"

# Demo-only: forget the checkpoint so the sample case can be replayed
curl -X POST "${H[@]}" "$BASE/applications/SYN-SHB-2026-0001/income-verification/reset"
```

## API surface

See `../docs/api.md` for the full table (case-management + backward-compat
fixed-demo endpoints).

## Architecture

```
Underwriter UI
      │ open case
      ▼
Orchestrator Agent  (LangGraph state machine, retry/timeout, no domain logic)
      │ dispatch
      ├──────────────┬──────────────┐
      ▼              ▼              ▼
Document Agent   Income Agent   Policy Agent
      └──────────────┴──────────────┘
                     ▼
            Consistency Agent
                     ▼
         Recommendation Builder
                     ▼
          Human Review Gate  (approve / edit / reject — never auto-executed)
                     ▼
            Action Executor  (rule-based, idempotent, mock LOS/DMS/Workflow/Notification)
```

Implementation-accurate architecture: `../docs/architecture-current.md`.
Original target-design docs: `../docs/ARCHITECTURE.md`,
`../docs/RAG-ARCHITECTURE.md`, `../docs/WORKFLOW.md`, `../docs/PHASES.md`.

## Tests

```bash
source .venv/bin/activate
pytest tests/ -q
```

46 tests, ~3s, no network calls required (`../docs/test-cases.md`).
