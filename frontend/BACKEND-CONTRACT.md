# Frontend ↔ Backend contract (as implemented)

This frontend calls the real FastAPI service in `backend/app`. There is no
mock/timer simulation left in `app.js` — every pipeline step, number and
citation shown on screen comes from a live API response.

## Auth (MVP header boundary)

Every request needs:

```http
X-Role: UNDERWRITER
X-Reviewer-Id: <reviewer-id>
```

`app.js` sends `X-Reviewer-Id: LT-01` for the demo reviewer "Linh Trần".

## Endpoints used

```http
POST /api/v1/applications/{application_id}/income-verification            # start/resume the workflow (runs the full agent graph)
POST /api/v1/applications/{application_id}/income-verification/reset      # demo-only: forget the in-memory checkpoint so the sample case can rerun
GET  /api/v1/income-verifications/{case_id}                               # full CaseContext: extracted fields, income analysis, policy result, findings, recommendation, proposed actions, execution results, audit_events
POST /api/v1/income-verifications/{case_id}/review                        # human decision: ACCEPT_ACTIONS | EDIT_AND_RERUN | MANUAL_HANDLING
GET  /api/v1/income-verifications/{case_id}/evidence
GET  /api/v1/income-verifications/{case_id}/audit
```

The MVP demo is pinned to one synthetic application, `SYN-SHB-2026-0001`
(case `SYN-IV-001`), backed by the fixtures under `dataset/`. This is an
intentional safety boundary documented in `docs/BACKEND-MVP-STATUS.md`: a
real application only opens once DMS/object-storage/OCR adapters exist.

## How the UI stays honest to the backend

- The pipeline animation in `runAssessment()` is cosmetic pacing only — every
  label, number and citation it reveals is read from the `GET
  /income-verifications/{case_id}` response, not hard-coded.
- Evidence buttons open real `EvidenceCitation` / `PolicyCitation` records
  (`document_name`, `page_number`, `quote`) from the case payload.
- The Human Review modal shows the actual `recommendation` (declared /
  average / eligible income, findings) and the actual `proposed_actions` the
  backend generated — never a fixed loan limit. The backend's job is income
  verification, not a credit decision, so the UI never states an approved
  loan amount.
- "Chấp thuận & thực thi" submits `ACCEPT_ACTIONS` with every proposed
  action id; the resulting `execution_results` (LOS/DMS/Workflow/Notification)
  are what light up the systems row.
- "Yêu cầu chỉnh sửa" submits `EDIT_AND_RERUN` with an operator-entered
  `edited_eligible_income`, which re-enters `BUILDING_RECOMMENDATION` and
  comes back to `HUMAN_REVIEW` with an updated recommendation.
- "Từ chối" submits `MANUAL_HANDLING`; the case moves to
  `MANUAL_REVIEW_REQUIRED` and the Action Executor never runs.
