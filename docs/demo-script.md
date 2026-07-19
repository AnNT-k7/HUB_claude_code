# Demo script (3–5 minutes)

## Setup (before the audience arrives)

```bash
# Terminal 1
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000

# Terminal 2
cd frontend && python3 -m http.server 8080
```

Open `http://localhost:8080`. Confirm the top-right pill reads
**"LLM TRỰC TIẾP · FPT"** (not "CHẾ ĐỘ MOCK") — if it says mock, check
`FPT_API_KEY`/`LLM_PROVIDER` in `.env`.

## 1. Show the case list is real, not a fixed demo (30s)

Point out: **"Danh sách hồ sơ"** is empty (or shows whatever was seeded)
and reads from a real SQLite database, not a hardcoded record. This is the
first thing to establish, since it's the single biggest gap the previous
version had — one fixed case, no intake path.

## 2. Create a new case (45s)

Click **"Tạo hồ sơ mới"**. Fill in a customer name, employer, requested
amount, loan term. Upload 3–4 small text/PDF files — the fastest option for
a live demo is to use one of the 20 pre-generated synthetic bundles under
`backend/data/synthetic_cases/case_01_fully_valid/` (run
`python3 scripts/generate_synthetic_cases.py` beforehand if that folder
doesn't exist yet). Click **"Tạo hồ sơ & tải tài liệu"**.

You land on the case detail screen with the pipeline diagram, all agents in
their idle state, and a hero card showing the just-entered customer info —
**note this is real data, not the old hardcoded "300 triệu ₫ / 36 tháng"**.

## 3. Run the pipeline — and don't rush past the wait (60–90s)

Click **"Chạy pipeline"**. The status pill counts up in real seconds and
says explicitly that this is a live LLM/RAG call, not an animation —
**this pause is the point**: it's genuine LLM extraction + real
cosine-similarity policy retrieval happening, typically 10–40 seconds. When
it returns, the pipeline nodes reveal in sequence with the actual returned
data (income figures, citation counts, finding counts) — this reveal is
fast because the data already arrived; say so explicitly if asked.

## 4. Open the evidence (30s)

Click any log entry's document icon, or a Document/Income/Policy node's
result. The evidence modal shows the exact document, page, and quoted text
backing that fact — click through 2–3 to make the point that every number
traces back to a verbatim source quote, not an LLM assertion.

## 5. Open Documents and Audit trail (30s)

Click **"Tài liệu"** — shows every uploaded file with its classification
method (`LLM` vs `KEYWORD_FALLBACK`) and a working download link. Click
**"Audit trail"** — shows the full append-only event log for this case
(`CASE_CREATED`, `DOCUMENT_UPLOADED`, `COMPONENT_COMPLETED` per agent,
`STATE_TRANSITION`, etc.) — point out both endpoints existed in the
original API but were never called from the old UI.

## 6. Human review (45s)

Click **"Mở kiểm duyệt"**. Show the recommendation status, findings (if
any), and proposed actions. Check the three confirmation boxes, add a
review note, click **"Chấp thuận & thực thi"**. Watch the systems chips
light up (LOS/DMS/Workflow/Notification/Audit) and the case reach
`COMPLETED`.

Alternative path to show if there's time: go back to the case list, create
a second case using `case_08_volatile_income` or `case_11_foreign_currency_salary`'s
bundle, run it, and show it correctly stops at a finding/`MANUAL_REVIEW_REQUIRED`
instead of a false "verified" — this demonstrates the system says "I don't
know, ask a human" instead of guessing.

## 7. Close (15s)

One sentence: every case here is independently created, every document was
just uploaded, every number came from a real LLM call and a real vector
search — verifiable live via `GET /api/v1/cases/system/status` — and
nothing gets written to a business system without an explicit human
approval.

## If something goes wrong live

- **LLM call times out or errors** → the pipeline falls back to regex
  extraction automatically; the case still produces a result, just with
  `parameter_extraction_method: "REGEX_FALLBACK"` visible in the Policy
  Agent's log line. Say so — it's the fallback working as designed, not a
  crash.
- **No network at the venue** → set `LLM_PROVIDER=mock` in `.env` before
  the talk and restart the backend; the mode pill will honestly show
  "CHẾ ĐỘ MOCK" and the pipeline still runs correctly end-to-end
  deterministically (this is exactly what `tests/test_synthetic_cases.py`
  exercises) — frame it as "here's the offline fallback mode" rather than
  hiding it.
