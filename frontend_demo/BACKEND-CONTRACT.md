# Backend Contract — Unsecured Income Verification

Tài liệu này ánh xạ frontend prototype sang backend realtime. Nguyên tắc quan trọng: agent chuyên môn chỉ đọc/biến đổi dữ liệu trong phạm vi task; chỉ `Action Executor` được gọi write API sau quyết định của con người.

## 1. Case state machine

```text
INGESTED
  -> UNDERWRITER_CONFIRMED
  -> ORCHESTRATING
  -> PARALLEL_ANALYSIS
  -> CONSISTENCY_CHECK
  -> RECOMMENDATION_READY
  -> PENDING_HUMAN_REVIEW
       -> REVISION_REQUESTED -> RECOMMENDATION_READY
       -> REJECTED
       -> APPROVED -> EXECUTING -> COMPLETED | EXECUTION_FAILED
```

Backend không được phát `APPROVED`, `EXECUTING` hoặc `COMPLETED` nếu chưa có `human_decision` hợp lệ và có danh tính người duyệt.

## 2. Component boundaries

- `Underwriter UI`: mở hồ sơ, xác nhận đầu vào, gửi quyết định human review.
- `Orchestrator Agent`: quản lý workflow, state, task dispatch, retry, timeout và routing; không tính kết quả chuyên môn và không gọi write API nghiệp vụ.
- `Document Agent`: trích xuất dữ liệu từ tài liệu.
- `Income Agent`: xác minh lương, dòng tiền và thu nhập ròng.
- `Policy Agent`: truy xuất quy định ngân hàng và trả citation.
- `Consistency Agent`: đối chiếu output có cấu trúc, phát hiện thiếu hoặc bất thường.
- `Recommendation Builder`: tạo kết quả, lý do và hành động đề xuất; không thực thi.
- `Human Review Gate`: chấp thuận, chỉnh sửa hoặc từ chối phiên bản đề xuất cụ thể.
- `Action Executor`: rule-based, scoped authorization, idempotent và có audit; ghi LOS/DMS/Workflow/Notification.

## 3. REST endpoints

### Cases and documents

```http
POST /api/v1/income-cases
GET  /api/v1/income-cases
GET  /api/v1/income-cases/{case_id}
POST /api/v1/income-cases/{case_id}/documents
POST /api/v1/income-cases/{case_id}/confirm-input
POST /api/v1/income-cases/{case_id}/verification/start
```

### Workflow reads

```http
GET /api/v1/income-cases/{case_id}/workflow
GET /api/v1/income-cases/{case_id}/tasks
GET /api/v1/income-cases/{case_id}/results
GET /api/v1/income-cases/{case_id}/recommendations/current
GET /api/v1/income-cases/{case_id}/citations
GET /api/v1/citations/{citation_id}
```

### Human decision and execution

```http
POST /api/v1/income-cases/{case_id}/decisions
POST /api/v1/income-cases/{case_id}/execution
GET  /api/v1/income-cases/{case_id}/execution/{execution_id}
```

Decision request:

```json
{
  "decision": "APPROVED | REJECTED | REVISION_REQUESTED",
  "recommendationVersion": 4,
  "feedback": "Xác nhận lại đơn vị công tác",
  "verifiedCitationIds": ["cit-policy-dti-4-3"],
  "idempotencyKey": "case-128-decision-v4"
}
```

Server phải từ chối quyết định trên recommendation cũ bằng `409 STALE_RECOMMENDATION`.

## 4. Realtime stream

```http
WS /api/v1/income-cases/{case_id}/stream
```

Event envelope:

```json
{
  "eventId": "evt_01",
  "caseId": "UV-2026-00128",
  "sequence": 42,
  "occurredAt": "2026-07-18T13:10:22.191Z",
  "type": "task.completed",
  "actor": { "type": "agent", "id": "income-agent" },
  "payload": {}
}
```

Required events:

```text
case.input_confirmed
workflow.created
task.dispatched
task.started
task.progressed
task.completed
task.failed
consistency.started
consistency.completed
recommendation.created
human_review.requested
human_decision.recorded
execution.started
execution.target_updated
execution.completed
evidence.attached
```

Frontend dùng `sequence` để sắp đúng thứ tự và resume bằng `?afterSequence=42` khi reconnect.

## 5. Structured agent outputs

```json
{
  "taskId": "task-income-01",
  "agentType": "INCOME",
  "status": "COMPLETED",
  "result": {
    "declaredNetMonthlyIncome": 31800000,
    "verifiedNetMonthlyIncome": 31200000,
    "salaryCreditMonths": 6,
    "varianceAmount": 600000,
    "varianceAccepted": true
  },
  "citationIds": ["cit-income-bank-statement-6m"],
  "inputVersion": 3,
  "completedAt": "2026-07-18T13:10:22.191Z"
}
```

Consistency output phải tham chiếu `taskId` và `inputVersion` của cả ba agent để recommendation có thể audit đầy đủ.

## 6. Action Executor safeguards

- Kiểm tra decision signature, role và recommendation version.
- Mọi target update dùng idempotency key riêng.
- Allowlist field được ghi cho từng hệ thống đích.
- Không cho agent chuyên môn giữ credential ghi LOS/DMS.
- Lưu request hash, response hash, người duyệt và correlation ID vào Audit.
- Retry có backoff; không lặp lại side effect đã thành công.
- Nếu một target lỗi, trả trạng thái từng target thay vì báo hoàn tất giả.

## 7. Minimal persistence model

```text
income_cases
case_documents
workflow_runs
agent_tasks
agent_results
consistency_reports
recommendations (versioned)
citations
human_decisions
execution_runs
execution_targets
audit_events (append-only)
```

Frontend hiện tại là simulation; khi nối backend, thay timer trong `app.js` bằng stream events nhưng giữ nguyên state names và node IDs để không phải dựng lại UI.
