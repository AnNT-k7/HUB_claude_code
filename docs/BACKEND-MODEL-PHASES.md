# Lộ trình triển khai (Roadmap) - Team Backend & Model

Tài liệu này chia nhỏ công việc của dự án **Income Verification Expert** tập trung hoàn toàn vào ranh giới trách nhiệm của **Team Backend & AI Model**. 

Các công việc liên quan đến giao diện (Next.js, UI Components) của Team Frontend đã được loại bỏ để team Backend/Model tập trung thiết kế dữ liệu, API, và logic suy luận của tác tử (Agents).

---

## Tổng quan các Phase

- **Phase 1:** Nền tảng dữ liệu chính sách và Policy Agent (RAG)
- **Phase 2:** Nhận diện, Trích xuất tài liệu và Động cơ tính toán thu nhập
- **Phase 3:** Điều phối Workflow (Planning), Đối chiếu (Review) và Tổng hợp
- **Phase 4:** Tích hợp API, Action Executor và Logging

---

## Phase 1: Nền tảng Dữ liệu & Policy Agent (RAG)
**Trọng tâm:** Xây dựng kho tri thức chính sách và Agent chuyên tra cứu quy định nội bộ.

**Công việc Backend & Data:**
1. **Database Schema:** Thiết kế bảng `policy_embeddings` trên PostgreSQL (pgvector).
2. **Ingestion Pipeline:** 
   - Parse các file văn bản chính sách cấp tín chấp của tổ chức.
   - Băm nhỏ văn bản (chunking) theo chuẩn `POLICY_RULE`.
   - Gọi API Embeddings (FPT `Vietnamese_Embedding`) và lưu vào pgvector kèm metadata (product, domain, effective date).
3. **Query Engine (RAG):** Viết logic filter cứng theo tag phòng ban/domain trước khi search vector (tránh search chéo sang chính sách khác).

**Công việc Model / AI Agent:**
1. **Policy Agent Prompting:** Tạo system prompt cho Policy Agent nhận context hồ sơ và câu hỏi -> gọi RAG -> trả về chính sách áp dụng.
2. **Bắt buộc Trích dẫn:** Ràng buộc LLM phải trả về object JSON chứa `document_name`, `page_number`, `effective_date`, `quote` (Citation).

---

## Phase 2: Document Agent & Động cơ tính toán thu nhập
**Trọng tâm:** AI trích xuất thông tin gốc (Model) + Các hàm số học tính toán chuẩn xác (Backend).

**Công việc Model / AI Agent:**
1. **Document Agent:** 
   - Viết luồng đọc file PDF/Ảnh (OCR).
   - Thiết kế Prompt trích xuất entity: tên khách hàng, lương hợp đồng, dòng tiền sao kê.
   - Ràng buộc cấu trúc đầu ra: Trả về strict JSON chứa array `salary_transactions`. Mỗi record bắt buộc gắn `evidence_id` (trỏ đến tọa độ dòng trên chứng từ).
2. **Income Agent (Phân tích):** Dùng LLM để phân loại "Giao dịch nào có khả năng là lương", "Giao dịch nào là chuyển khoản nội bộ/rác".

**Công việc Backend (Deterministic Tools):**
1. **Income Calculator:** Viết code Python thuần để tính: trung bình 3 tháng, trung bình 6 tháng, tỷ lệ biến động (%). LLM **tuyệt đối không** tự cộng trừ nhân chia.
2. **Tool Integration:** Tích hợp Income Calculator vào Income Agent (Agent gọi Tool truyền mảng số liệu, Tool trả về kết quả để Agent gắn vào state).

---

## Phase 3: Điều phối Workflow & Consistency Agent
**Trọng tâm:** Xây dựng xương sống của toàn hệ thống đa tác tử (Multi-Agent State Machine).

**Công việc Backend (Orchestration):**
1. **State Machine (`orchestrator.py`):** 
   - Code logic quản lý chuyển đổi trạng thái (từ `FETCHING_DOCUMENTS` -> `COMPLETED`).
   - Khởi tạo và quản lý `CaseContext` (chia namespace cho từng Agent).
   - Bắt exception (Lỗi gọi API LLM, thiếu dữ liệu đầu vào) để routing chuyển sang `PENDING_HUMAN_REVIEW` thay vì crash hệ thống.

**Công việc Model / AI Agent:**
1. **Consistency Agent (Reviewer Agent):**
   - Đọc kết quả từ Document, Income, Policy.
   - Đối chiếu chéo (Ví dụ: So sánh *Lương thực nhận* với *Lương trong Hợp đồng*, So sánh *Đơn vị chuyển khoản* với *Employer*).
   - Sinh ra mảng `findings` (cảnh báo) kèm mức độ (INFO, WARNING, CRITICAL).
2. **Recommendation Builder:**
   - Đóng gói toàn bộ data thành báo cáo.
   - Rule-based (kết hợp LLM) để sinh ra `proposed_actions` (Ví dụ: Thiếu giấy tờ X -> Tạo action yêu cầu bổ sung X).

---

## Phase 4: Action Executor, API Gateway & Audit
**Trọng tâm:** Giao tiếp với Frontend và tích hợp ra các hệ thống bên ngoài một cách an toàn.

**Công việc Backend & Integrations:**
1. **Action Executor:** 
   - Viết service nhận action id đã được con người duyệt (`APPROVED`).
   - Validate quyền thực thi, check idempotency (chống click dup).
   - Code các class giả lập (Mock) gọi hệ thống LOS, DMS, Notification.
2. **REST API Gateway (`api/v1/income_verifications.py`):** 
   - Endpoint tạo mới phiên làm việc.
   - Endpoint trả về `CaseContext` (cho Frontend render UI).
   - Endpoint nhận `Human Review` (Chuyên viên Approve/Reject).
3. **Audit Service:** Ghi log toàn bộ hoạt động (Agent chạy giờ nào, Output ra sao, Con người bấm nút gì) vào bảng `audit_logs`.

---

## Bảng tiêu chí Hoàn thành (Definition of Done - DoD)
- Toàn bộ Agent Output phải đúng chuẩn JSON/Pydantic Schema.
- Không có bất kỳ phép toán số học nào do LLM tự suy nghĩ.
- Code backend phải có Unit Test cho phần Calculator và Action Executor chặn quyền.
- Hoàn thiện bộ API Docs (Swagger/OpenAPI) để bàn giao cho team Frontend.
