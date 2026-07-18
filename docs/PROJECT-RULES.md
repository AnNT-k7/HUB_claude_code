# Project Rules — Income Verification Expert

**Project:** Income Verification Expert — Trợ lý xác minh thu nhập tín chấp

**Enforcement:** Bắt buộc cho thiết kế, code, test và pull request

**Source of truth:** `PRD.md` → `ARCHITECTURE.md` → `RAG-ARCHITECTURE.md` → `WORKFLOW.md` → `PHASES.md`

---

## 1. Tuân thủ phạm vi

- Actor duy nhất là **chuyên viên thẩm định tín chấp**.
- Task duy nhất là **kiểm tra và xác minh thu nhập từ bộ hồ sơ vay**.
- Không thêm CIC, KYC/AML, pháp lý, rủi ro ngành, tài sản bảo đảm, chấm điểm tín dụng, hạn mức, hợp đồng tín dụng hoặc giải ngân.
- Hệ thống không phê duyệt hoặc từ chối khoản vay.
- Nếu code cũ mâu thuẫn với docs 2.x, docs 2.x là target architecture; code cũ được xem là legacy cần migration.

## 2. Thành phần được phép

Workflow chỉ gồm:

1. `Orchestrator`;
2. `DocumentAgent`;
3. `IncomeAnalysisAgent`;
4. `PolicyAgent`;
5. `ConsistencyAgent`;
6. `RecommendationBuilder`;
7. `HumanReviewGate`;
8. `ActionExecutor`.

Không dùng Reviewer/Debate Agent hoặc các agent phòng ban của kiến trúc Digital Expert Agents cũ trong target MVP.

Orchestrator chỉ quản lý workflow, state, routing, retry và schema. Orchestrator không được tự tính thu nhập, tự diễn giải policy hoặc gọi API mutation.

Các specialist không nhắn prompt tự do cho nhau. Tất cả giao tiếp qua typed `CaseContext`; mỗi component chỉ cập nhật namespace do mình sở hữu.

## 3. Typed contract và trạng thái

Python dùng Pydantic v2; TypeScript bật strict mode. Không dùng `Any`/`any` trong domain contract nếu có thể mô hình hóa cụ thể.

Citation tối thiểu:

```python
from datetime import date
from pydantic import BaseModel


class EvidenceCitation(BaseModel):
    document_id: str
    document_name: str
    page_number: int
    section_id: str | None = None
    evidence_id: str
    quote: str


class PolicyCitation(BaseModel):
    document_name: str
    page_number: int
    section_id: str
    effective_date: date
    quote: str
    chunk_id: str
```

Kết quả thiếu hoặc lỗi phải dùng status rõ ràng như `MISSING_DOCUMENTS`, `POLICY_NOT_FOUND`, `MANUAL_REVIEW_REQUIRED` hoặc `TECHNICAL_ERROR`. Không biến missing data thành kết quả thành công.

## 4. Tính toán deterministic

- LLM không được cộng, chia, tính trung bình, độ biến động, chênh lệch hoặc tự quy đổi currency.
- Income calculator phải nhận structured facts đã validate và trả input trace, period, currency, công thức, rounding rule và calculation version.
- Không bù kỳ thiếu, suy đoán giao dịch lương hoặc gộp currency khác nhau.
- Ngưỡng nghiệp vụ phải đến từ policy/rule version đã phê duyệt, không hard-code trong prompt.
- Mọi công cụ tính toán và rule engine có unit test cho missing values, zero/empty inputs, period mismatch, currency mismatch và rounding boundary.

## 5. RAG và bằng chứng

- Global `policy_embeddings` chỉ chứa chính sách nội bộ đã kiểm duyệt; không chứa PII hoặc tài liệu khách hàng.
- Policy query bắt buộc lọc `domain`, `product`, `chunk_type`, trạng thái phê duyệt và ngày hiệu lực.
- Runtime query dùng cùng embedding provider/model/dimension với indexing.
- Mọi policy conclusion phải có exact citation.
- Không tìm thấy policy, policy hết hiệu lực hoặc policy conflict phải chuyển human review.
- Customer evidence phải tách theo `case_id`; không được query chéo hồ sơ.
- Mọi extracted fact phải truy ngược được tài liệu, trang/vùng dữ liệu và `evidence_id`.

## 6. Human-in-the-loop và action permissions

### 6.1. Được tự động

Chỉ các thao tác read-only hoặc artifact nội bộ có thể đảo ngược:

- lấy tài liệu theo quyền từ Mock DMS;
- tạo draft phiếu xác minh;
- đính kèm evidence vào draft;
- tạo task/nhãn nội bộ có idempotency và audit;
- chuyển vào queue review nội bộ mà không thay đổi kết quả chính thức.

### 6.2. Bắt buộc human approval

- gửi yêu cầu bổ sung hồ sơ ra ngoài;
- ghi nhận thu nhập đủ điều kiện chính thức;
- ghi chú chính thức vào LOS;
- đóng bước xác minh;
- chuyển hồ sơ sang công đoạn tiếp theo;
- mọi external mutation hoặc official workflow transition.

### 6.3. Bị cấm

- phê duyệt/từ chối khoản vay;
- thay đổi hạn mức hoặc bỏ qua policy;
- sửa/xóa tài liệu nguồn;
- gọi production endpoint trong MVP;
- để LLM tự tạo endpoint, credential hoặc mutation payload.

Action Executor là service rule-based. Mỗi action phải validate schema, authorization, state precondition, permission class và idempotency key; sau đó verify kết quả và ghi audit.

## 7. Dữ liệu, riêng tư và audit

- Mọi dữ liệu khách hàng được cô lập theo `case_id` và `application_id`.
- Không ghi secret vào source, fixture, prompt, docs hoặc log.
- Không đưa customer PII vào long-term LLM memory hoặc global vector index.
- Audit là append-only và ghi actor, event, timestamp, workflow/rule/calculation version, input/output reference và result.
- Audit/log phải mask PII và secret; không mặc định lưu toàn bộ raw document hoặc full prompt payload.
- Mọi agent execution, state transition, policy query, human review và action execution phải có audit event.
- Phản hồi chuyên viên không tự động trở thành training data.

## 8. Layer boundaries

- `frontend/`: presentation, API state và evidence viewer; không chứa policy hoặc calculation logic.
- `backend/app/api/`: authentication/authorization, request validation và response formatting.
- `backend/app/agents/`: orchestration và specialist reasoning trên typed state.
- `backend/app/tools/`: calculation/rule engine deterministic.
- `backend/app/services/`: storage, RAG, Action Executor và integration adapters.
- `backend/app/db/`: persistence, transaction và migrations.
- `backend/app/mock_apis/`: Mock LOS/DMS/Workflow/Notification cho MVP.

Agent không được gọi trực tiếp database mutation hoặc external API; phải đi qua service/tool interface được cấp quyền.

## 9. Retry, idempotency và failure handling

- Chỉ retry technical/transient failure; không retry để che missing evidence hoặc policy not found.
- Retry phải có `max_attempts`, timeout và backoff.
- Workflow checkpoint sau state transition quan trọng.
- External action có idempotency key và verify-before-retry.
- Không được tự coi max-retry là kết quả xác minh thành công.

## 10. Kiểm thử và definition of done

Mỗi thay đổi chỉ hoàn thành khi:

- schema và state transition bị ảnh hưởng đã được cập nhật;
- happy path, missing evidence, policy not found, mismatch và technical error có test;
- deterministic calculation/routing/permissions có unit test;
- integration adapter có contract test bằng mock;
- human gate và audit vẫn nguyên vẹn;
- không có stale reference sang kiến trúc cũ trong tài liệu bị ảnh hưởng;
- focused checks pass và mọi stub/blocker được báo rõ.

Không tuyên bố end-to-end ready khi target modules trong `ARCHITECTURE.md` chưa được triển khai.
