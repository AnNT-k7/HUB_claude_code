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
anything is written to a business system.

## What's in this repo

| Path | What it is |
| --- | --- |
| `backend/` | FastAPI + LangGraph multi-agent workflow (Document, Income, Policy, Consistency, Recommendation, Human Review, Action Executor) |
| `frontend/` | The command-center UI — a dependency-free static app wired to the live backend API (no build step, no simulation) |
| `dataset/` | Synthetic case dossier + policy corpus the demo agents read from |
| `docs/` | Design docs: architecture, RAG design, workflow, phased roadmap, project rules |

## Architecture

```
Underwriter UI  ──open case──▶  Orchestrator Agent
                                  (LangGraph state machine; retry/timeout/routing only,
                                   no domain logic, no write access)
                                       │ dispatch (parallel)
                        ┌──────────────┼──────────────┐
                        ▼              ▼              ▼
                 Document Agent   Income Agent    Policy Agent
                (extracts dossier) (salary/cash-flow) (SHB policy RAG + citations)
                        └──────────────┴──────────────┘
                                       ▼
                              Consistency Agent
                       (cross-checks the 3 outputs, flags gaps/anomalies)
                                       ▼
                          Recommendation Builder
                    (evidence-backed verification result — never a loan decision)
                                       ▼
                           Human Review Gate
                (underwriter: approve / edit eligible income / reject — required)
                                       ▼
                            Action Executor
        (rule-based, idempotent, scoped — writes to LOS / DMS / Workflow / Notification,
                    only after an identified human approval; append-only audit)
```

Every specialist agent is read/compute-only inside its task scope. Only the
Action Executor is allowed to call the (mocked) bank systems, and only after
a human decision — see `AGENTS.md` and `docs/PROJECT-RULES.md` for the full
guardrails this system is built to respect (it never approves/rejects a
loan, sets a credit limit, or disburses funds).

## Quickstart

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi "uvicorn[standard]" pydantic pydantic-settings \
  langgraph sqlalchemy pgvector langchain-core httpx python-dotenv
uvicorn app.main:app --reload --port 8000
```

No database, object storage or LLM API key is required to run the shipped
demo case — see `backend/README.md` for why, and for the full
production-grade `requirements.txt` if you want to extend past the demo.

### 2. Frontend

```bash
cd frontend
python3 -m http.server 8080
```

Open `http://localhost:8080`.

### 3. Run the sample case

The demo ships with one pre-loaded case: **Nguyễn Minh Anh**, application
`SYN-SHB-2026-0001` (case `SYN-IV-001`) — a synthetic 300M VND / 36-month
loan application with a full dossier (loan application, labor contract,
payroll, 6-month bank statement) under `dataset/`.

1. Click **Bắt đầu xác minh** — watch Document, Income and Policy agents run
   in parallel against the real backend, then Consistency Agent and
   Recommendation Builder produce an evidence-backed result.
2. Click **Mở kiểm duyệt** to review the recommendation, findings and
   proposed actions.
3. **Chấp thuận & thực thi** to approve and watch the Action Executor update
   LOS / DMS / Workflow / Notification (mock adapters) — or **Yêu cầu chỉnh
   sửa** / **Từ chối** to see the revision and manual-handling paths.
4. **Đặt lại** resets the backend's in-memory state so the same case can be
   replayed as many times as you like (useful for repeat demos/judging).

Every number, citation and log line in the UI is read from the live API
response — the pipeline animation only controls pacing, not content.

## Tech stack

- **Backend:** FastAPI, LangGraph (typed state machine + retry/timeout),
  Pydantic v2, SQLAlchemy (Postgres/pgvector for the production path),
  deterministic Python tools for arithmetic and consistency rules.
- **Frontend:** vanilla HTML/CSS/JS — no framework, no build step — so the
  entire UI ships as static files and is trivial to audit.
- **RAG:** an isolated, case-scoped policy corpus with exact citations
  (document, page, section, effective date) — no PII in the global policy
  index, per `docs/RAG-ARCHITECTURE.md`.

## Status and roadmap

This is an MVP demo of the income-verification expert, one of several
planned digital experts (credit, legal/compliance, products, operations).
See `docs/BACKEND-MVP-STATUS.md` for exactly what's done vs. what's still
needed before a production rollout (real IAM instead of demo headers, a
domain-owner-approved policy corpus, transactional checkpoint storage,
approved OCR/DMS adapters, append-only audit persistence).
