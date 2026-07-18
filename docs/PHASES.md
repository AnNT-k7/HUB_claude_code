# Lộ trình triển khai — Income Verification Expert

Tài liệu này rebaseline roadmap sau khi dự án thu hẹp về một actor và một task. Completion của các agent thuộc Digital Expert Agents cũ không được tính là completion của target MVP mới.

**Active phase:** Phase 2 — Income Policy RAG & Case Evidence Foundation

---

## Nguyên tắc roadmap

- Mỗi phase phải tạo ra contract và test có thể kiểm chứng.
- Không mở rộng sang CIC, KYC/AML, pháp lý, rủi ro, tài sản bảo đảm hoặc phê duyệt khoản vay.
- Hạ tầng/code cũ chỉ được tái sử dụng sau khi kiểm tra phù hợp với docs 2.x.
- Không tuyên bố phase hoàn thành nếu mới có stub, mock output tĩnh hoặc code của kiến trúc cũ.

## Tổng quan

- [x] **Phase 0: Scope & Architecture Rebaseline**
- [x] **Phase 1: Reusable Foundation Inventory**
- [ ] **Phase 2: Income Policy RAG & Case Evidence Foundation — ACTIVE**
- [ ] **Phase 3: Document Extraction & Deterministic Income Engine**
- [ ] **Phase 4: Agent Workflow & Typed Case Context**
- [ ] **Phase 5: Human Review & Action Executor**
- [ ] **Phase 6: REST API & Underwriter UI**
- [ ] **Phase 7: Evaluation, Audit & Demo Hardening**

---

## Phase 0: Scope & Architecture Rebaseline — COMPLETED

Đầu ra:

- PRD chốt một actor và một task;
- architecture chốt component boundaries, Case Context và Action Executor;
- project rules, RAG architecture và workflow được đồng bộ;
- legacy scope được đánh dấu ngoài phạm vi.

Điều kiện hoàn thành:

- không còn tài liệu nguồn nào bắt buộc 5–6 phòng ban, Reviewer/Debate hoặc Tier 3 contract generation;
- outbound/official write có human gate;
- state và component naming nhất quán.

## Phase 1: Reusable Foundation Inventory — COMPLETED

Các nền tảng có thể tái sử dụng sau migration:

- FastAPI/Next.js skeleton;
- PostgreSQL + pgvector;
- MinIO/object storage service;
- embedding service FPT `Vietnamese_Embedding` 1024 chiều;
- base database/session và mock integration framework.

Legacy modules hiện có như `tier2_board`, department specialists, Reviewer, DSCR/LTV calculator và credit contract operations không phải target implementation.

## Phase 2: Income Policy RAG & Case Evidence Foundation — ACTIVE

### Mục tiêu

Xây dựng corpus chính sách chỉ dành cho xác minh thu nhập và contract lưu evidence/facts theo case.

### Công việc

1. Thu thập policy/quy trình xác minh thu nhập tín chấp cá nhân đã được duyệt.
2. Gắn metadata: domain, product, chunk type, document version, page/section, effective/expiry date và approval status.
3. Chỉ index `POLICY_RULE` và `VERIFICATION_PROCEDURE` hợp lệ.
4. Implement query filter bắt buộc theo `RAG-ARCHITECTURE.md`.
5. Thiết kế `DOCUMENT_EVIDENCE` và `STRUCTURED_FACT` case-scoped.
6. Chặn customer PII khỏi global policy index.
7. Tạo retrieval benchmark và quality report.

### Definition of done

- corpus được domain owner duyệt;
- ingestion idempotent và quarantine metadata lỗi;
- query không thể bỏ domain/product/chunk type/effective-date filter;
- policy result trả citation đầy đủ;
- policy not found/conflict có deterministic status;
- tests cho isolation, metadata, filter và citation pass.

## Phase 3: Document Extraction & Deterministic Income Engine

### Công việc

- phân loại đơn vay, hợp đồng/phụ lục, bảng lương và sao kê;
- OCR/extract với evidence pointer đến page/row/bounding box;
- chuẩn hóa customer, employer, currency, period và salary transactions;
- xây income calculator cho average, variation và deviation;
- xây transaction classification/rule inputs có version;
- xử lý unreadable, missing periods và currency mismatch.

### Definition of done

- mỗi fact truy ngược được evidence;
- LLM không thực hiện số học;
- calculator có test cho edge cases và rounding;
- thiếu bằng chứng không tạo giá trị suy đoán;
- benchmark extraction đạt target PRD.

## Phase 4: Agent Workflow & Typed Case Context

### Công việc

- tạo target modules dưới `backend/app/agents/income_verification/`;
- triển khai Orchestrator, Document, Income, Policy, Consistency và Recommendation components;
- định nghĩa typed Case Context và namespace ownership;
- implement state machine, checkpoint, bounded retry và routing rules;
- loại bỏ phụ thuộc runtime vào legacy department pipeline cho flow mới.

### Definition of done

- happy path chạy end-to-end tới `HUMAN_REVIEW`;
- Income và Policy chạy song song khi đủ input;
- schema failure, missing docs, policy not found và mismatch có state rõ ràng;
- mọi agent turn/state transition có audit event;
- workflow tests pass mà không gọi live LLM.

## Phase 5: Human Review & Action Executor

### Công việc

- implement review outcomes: accept actions, edit/re-run và manual handling;
- permission matrix cho auto-reversible, human-required và prohibited actions;
- Action Executor validate quyền, precondition, idempotency và verify result;
- Mock DMS/LOS/Workflow/Notification adapters;
- audit và PII masking.

### Definition of done

- official/outbound action bị chặn khi thiếu human approval;
- action trùng không tạo side effect;
- production endpoint không thể được cấu hình trong MVP profile;
- contract tests cho success, failure, retry và ambiguous response pass.

## Phase 6: REST API & Underwriter UI

### Công việc

- API start/resume workflow, read Case Context, review, evidence và audit;
- UI một màn hình tổng hợp cho chuyên viên;
- evidence viewer và policy citation viewer;
- editor cho facts/actions và reason capture;
- polling hoặc event update cho workflow state.

### Definition of done

- UI không chứa policy/calculation logic;
- role/case authorization được kiểm tra ở API;
- chuyên viên phân biệt rõ xác nhận kết quả AI với quyết định khoản vay;
- frontend typecheck/build và browser workflow tests pass.

## Phase 7: Evaluation, Audit & Demo Hardening

### Công việc

- xây benchmark tài liệu và expected outputs đã ẩn danh;
- đo extraction, salary classification, missing-document detection và latency;
- kiểm tra 100% kết luận trọng yếu có evidence/citation;
- diễn tập policy not found, conflict, document unreadable và duplicate action;
- chuẩn bị demo scenario trong PRD và runbook.

### Definition of done

- đạt evaluation targets hoặc có waiver được phê duyệt;
- audit trace đủ để tái dựng workflow;
- không có secret/PII trong fixtures, logs hoặc policy index;
- không còn critical stub/blocker trong demo path;
- docs và code mapping được kiểm tra lần cuối.
