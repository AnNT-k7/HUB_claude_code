# Income Verification Expert — Backend

FastAPI + LangGraph multi-agent backend for the unsecured-loan income
verification workflow. One actor (the underwriter), one task (verify income
from the loan dossier) — see `AGENTS.md` and `docs/PROJECT-RULES.md` for the
guardrails this service is built around.

## Quickstart (demo mode — no Postgres/MinIO/API keys required)

The shipped demo case (`SYN-SHB-2026-0001`) runs entirely offline: document
extraction reads a synthetic markdown fixture, policy retrieval reads a
pre-built local JSON corpus, income/consistency/recommendation logic is
deterministic Python, and the Action Executor writes to an in-memory mock
gateway. No LLM call is on this path, so no API key is needed to run the demo.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi "uvicorn[standard]" pydantic pydantic-settings \
  langgraph sqlalchemy pgvector langchain-core httpx python-dotenv
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for interactive OpenAPI docs.

> The full `requirements.txt` also covers the production path (Postgres +
> pgvector, MinIO, PDF/OCR extraction, embedding providers). Install it
> instead (`pip install -r requirements.txt`) if you're extending beyond the
> demo case — see `docs/BACKEND-MVP-STATUS.md` for what's still required
> before that path is production-ready.

## Exercising the sample case

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

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/applications/{application_id}/income-verification` | Start/resume the workflow |
| `POST` | `/api/v1/applications/{application_id}/income-verification/reset` | Demo-only: reset the in-memory checkpoint |
| `GET` | `/api/v1/income-verifications/{case_id}` | Full case context |
| `POST` | `/api/v1/income-verifications/{case_id}/review` | Human decision: `ACCEPT_ACTIONS` \| `EDIT_AND_RERUN` \| `MANUAL_HANDLING` |
| `POST` | `/api/v1/income-verifications/{case_id}/retry-actions` | Retry a failed execution |
| `GET` | `/api/v1/income-verifications/{case_id}/evidence` | Evidence citations |
| `GET` | `/api/v1/income-verifications/{case_id}/audit` | Append-only audit trail |

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

Full design docs: `docs/ARCHITECTURE.md`, `docs/RAG-ARCHITECTURE.md`,
`docs/WORKFLOW.md`, `docs/PHASES.md`.

## Tests

```bash
source .venv/bin/activate
pip install pytest
pytest tests/
```
