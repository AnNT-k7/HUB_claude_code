# Trợ lý xác minh thu nhập tín chấp — Frontend

Dependency-free static UI (no build step) that drives the real FastAPI
backend in `../backend`. This is the command-center visualization for the
multi-agent income-verification pipeline.

## Run

1. Start the backend first (see `../backend/README.md` or the root
   `README.md`) — by default on `http://localhost:8000`.
2. Serve this folder over HTTP (opening `index.html` via `file://` will hit
   CORS/module issues in some browsers):

   ```bash
   cd frontend
   python3 -m http.server 8080
   ```

3. Open `http://localhost:8080`.

If your backend runs on a different port, override it from the browser
console before interacting with the page:

```js
localStorage.setItem('iv_api_base', 'http://localhost:8020/api/v1');
location.reload();
```

## Main demo path

1. **Trung tâm điều phối** loads with the one built-in sample case
   (`SYN-IV-001` / application `SYN-SHB-2026-0001`, customer Nguyễn Minh Anh).
2. Click **Bắt đầu xác minh** — the Underwriter UI opens the case, the
   Orchestrator starts the real LangGraph workflow, and Document / Income /
   Policy agents run in parallel against the synthetic dataset.
3. Consistency Agent cross-checks the three outputs; Recommendation Builder
   produces an evidence-backed income-verification recommendation (never a
   credit decision).
4. Click **Mở kiểm duyệt** to open the Human Review Gate. Approve, request an
   edited eligible-income figure, or reject.
5. Only after **Chấp thuận & thực thi** does the Action Executor call the
   mock LOS/DMS/Workflow/Notification gateways and the case reaches
   `COMPLETED`.
6. **Đặt lại** resets both the UI and the backend's in-memory checkpoint so
   the sample case can be replayed end to end as many times as you like.

## Views

- **Trung tâm điều phối:** pipeline, parallel analysis, consistency check,
  recommendation, Human Review Gate and Action Executor — all backed by live
  API calls.
- **Hồ sơ tín chấp:** live status of the one sample case (workflow state,
  audit event count).

## Files

- `index.html` — semantic UI structure and both views.
- `styles.css` — visual system, layout, motion, component states.
- `app.js` — real API client + orchestration animation (see
  `BACKEND-CONTRACT.md` for the exact endpoints and payloads).
- `BACKEND-CONTRACT.md` — the contract this frontend actually relies on.

## Design direction

- Dark navy banking operations command center with legible realtime status.
- Specialist agents never write directly to business systems.
- Action Executor stays locked until an identified human decision is
  recorded, and every state shown was actually produced by the backend.
