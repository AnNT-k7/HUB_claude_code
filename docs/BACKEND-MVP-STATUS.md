# Backend MVP status — Income Verification Expert

Ngày cập nhật: 2026-07-18

## Đã hoàn thiện trong flow demo

- `Document Agent` trích xuất hồ sơ synthetic theo `case_id`, facts, salary transactions, payroll variable income và evidence.
- `Income Analysis Agent` phân loại giao dịch, tính average/variation/anomaly bằng deterministic tools.
- `Policy Agent` truy vấn corpus Policy cô lập, kiểm tra domain/product/scope/approval/effective date và trả citation đầy đủ.
- `Consistency Agent` đối chiếu declared/contract/recognized/eligible income, employer, currency, period, missing documents và anomaly.
- `Recommendation Builder` tạo report draft và action typed.
- `Human Review Gate` hỗ trợ `ACCEPT_ACTIONS`, `EDIT_AND_RERUN`, `MANUAL_HANDLING`.
- `Action Executor` kiểm tra permission, state, human approval, idempotency, mock gateway, verify và retry kỹ thuật.
- REST API demo chạy qua typed `CaseContext`, không còn dùng `MOCK_DB` trong target route.
- Case-scoped document storage boundary, checkpoint/action/audit SQL models và migration đã có.

## API MVP

Tất cả endpoint yêu cầu header demo:

```text
X-Role: UNDERWRITER
X-Reviewer-Id: <reviewer-id>
```

- `POST /api/v1/applications/{application_id}/income-verification`
- `GET /api/v1/income-verifications/{case_id}`
- `POST /api/v1/income-verifications/{case_id}/review`
- `POST /api/v1/income-verifications/{case_id}/retry-actions`
- `GET /api/v1/income-verifications/{case_id}/evidence`
- `GET /api/v1/income-verifications/{case_id}/audit`

MVP demo hiện chạy bộ hồ sơ synthetic `SYN-SHB-2026-0001`. Đây là giới hạn an toàn có chủ ý; hồ sơ thật chỉ được mở khi DMS/object-storage/OCR adapter đã được cấu hình.

## Còn cần domain/infrastructure trước production

- thay policy `APPROVED_FOR_DEMO` bằng corpus đã domain owner phê duyệt;
- chạy migration trên PostgreSQL và thay `InMemoryCheckpointStore` bằng repository giao dịch;
- thay header demo bằng IAM/role authorization thực tế;
- nối MinIO/DMS và OCR được phê duyệt cho PDF scan/ảnh;
- triển khai audit append-only vào database với PII masking/retention;
- chạy benchmark extraction/retrieval/latency theo Phase 7.

Không có mục nào trong production backlog được phép làm thay đổi phạm vi sang phê duyệt khoản vay, hạn mức, hợp đồng tín dụng hoặc giải ngân.
