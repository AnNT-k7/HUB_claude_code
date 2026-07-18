# Lộ trình Triển khai Digital Expert Agents (Phases)

Tài liệu này liệt kê các giai đoạn (Phases) còn lại để hoàn thành hệ thống bản MVP và hướng dẫn chi tiết cách lập trình cho từng Phase, bắt đầu từ Phase 2.

---

## Tổng quan Lộ trình (Roadmap)

- [x] **Phase 1: Foundation (ĐÃ HOÀN THÀNH)**
  - Chốt Kiến trúc (PRD, RAG Architecture, AI Rules).
  - Thiết lập hạ tầng Docker (PostgreSQL pgvector, MinIO).
  - Khai báo 7 bảng cơ sở dữ liệu (`models.py`) và setup Session.
  - Dựng khung folder Frontend & Backend Stubs.

- [x] **Phase 2: RAG & Storage Core (Làm nền tảng dữ liệu) — ĐÃ HOÀN THÀNH**
  - Viết dịch vụ upload/download file gốc lên MinIO (`services/storage.py`).
  - Xây dựng luồng cắt (chunking) theo 5 loại taxonomy chuẩn và nhúng (embedding) 2.486 chunks chính sách ngân hàng vào pgvector (`policy_embeddings`).

- [ ] **Phase 3: LangGraph & Tier 2 Specialist Agents (Khối óc phân tích)**
  - Lập trình 5 Specialist Agents (Customer Relationship, Credit, Risk Management, Legal & Compliance, Collateral Appraisal).
  - Lập trình Reviewer Agent (Debate & Cross-checking Engine).

- [ ] **Phase 4: Tier 1 Orchestrator & Tier 3 Operations (Điều phối & Vận hành)**
  - Lập trình Banking Orchestrator chia nhỏ tác vụ.
  - Lập trình Operations Agent sinh draft hợp đồng và gọi Mock Core SHB.

- [ ] **Phase 5: REST API Gateway**
  - Hoàn thiện các file controller (`cases.py`, `orchestrator.py`, `operations.py`).

- [ ] **Phase 6: Frontend UI Dashboard**
  - Kết nối hook và dựng UI theo dõi Shared Board, hiển thị tranh luận.

---

## Hướng dẫn Chi tiết: Triển khai Phase 2 (RAG & Storage Core)

Mục tiêu cốt lõi của Phase 2 là xây dựng kho chứa dữ liệu file vật lý (MinIO) và kho lưu trữ tri thức AI (PostgreSQL pgvector). 

### CÂU HỎI QUAN TRỌNG: Lấy dữ liệu (Files/Data) từ đâu?

Hệ thống của chúng ta xử lý 2 luồng dữ liệu riêng biệt. Tương ứng, nguồn lấy file (data source) cũng khác nhau:

#### Luồng 1: Dữ liệu Chính sách nội bộ (Dùng để nạp kiến thức RAG)
Đây là các file Quy chế tín dụng, Quy trình KYC, Chính sách Tài sản bảo đảm (Dùng làm "não bộ" để các agent đối chiếu).
*   **Lấy từ đâu (Lúc Dev):** 
    *   Tạo một thư mục tĩnh tại `backend/data/mock_policies/`.
    *   Trong thư mục này, chúng ta sẽ tự tạo ra 1 vài file `.md`, `.txt` hoặc `.pdf` giả lập chứa các đoạn text chính sách mẫu của ngân hàng.
*   **Quy trình xử lý (Indexing):**
    *   Lập trình viên viết một script nhỏ (ví dụ `backend/scripts/seed_rag.py`).
    *   Script này duyệt qua thư mục `mock_policies/`, đọc file.
    *   Sử dụng code trong `rag.py` để cắt file theo đúng **5 loại Chunk chuẩn** (đã định nghĩa trong `RAG-ARCHITECTURE.md`).
    *   Gọi OpenAI Embeddings để sinh vector và lưu thẳng vào bảng `policy_embeddings` trong PostgreSQL.

#### Luồng 2: Dữ liệu Hồ sơ Khách hàng cụ thể (`CASE_EVIDENCE`)
Đây là các file Báo cáo tài chính, Hợp đồng, Giấy đăng ký kinh doanh mà một Doanh nghiệp cụ thể nộp lên xin vay vốn.
*   **Lấy từ đâu (Lúc Dev & Lúc chạy thực tế):**
    *   **Frontend Upload:** Người dùng (Banking Officer) sẽ chọn file trên màn hình máy tính và kéo thả vào khu vực `DocumentUploadZone.tsx` trên Frontend web.
    *   **API Gateway:** Frontend gọi API `POST /api/v1/cases/documents` truyền file (multipart form data) lên Backend.
    *   **Lưu trữ MinIO:** Hàm `upload_document()` trong `services/storage.py` nhận bytes của file và lưu thẳng vào bucket MinIO (vd: `s3://loan-documents/case-uuid/BCTC_2025.pdf`).
    *   Khi chạy AI, Orchestrator sẽ lấy file này từ MinIO tải về RAM, bóc tách ra text để 5 Specialist Agents tiến hành phân tích (`STRUCTURED_FACT`).

---

### Các bước code cụ thể cho Phase 2 (To-Do List)

1. **Chuẩn bị Thư viện:**
   * Thêm thư viện gọi S3: Cần thêm `minio` hoặc `boto3` vào `requirements.txt`.
   * Thêm thư viện LangChain & OpenAI: Cần thêm `langchain-openai`, `langchain-text-splitters`.

2. **Viết `backend/app/services/storage.py` (Xử lý Luồng 2):**
   * Định nghĩa Class `StorageService`.
   * **`upload_document(file_bytes, filename)`**: Đẩy file lên MinIO bucket (tạo bucket nếu chưa có), trả về đường dẫn `s3://...`.
   * **`get_document_bytes(storage_path)`**: Download file từ MinIO về RAM để AI đọc.

3. **Chuẩn bị Dữ liệu mẫu (Cho Luồng 1):**
   * Tạo thư mục `backend/data/mock_policies/`.
   * Tạo file `quy_che_tin_dung_doanh_nghiep.txt` và soạn thử vài đoạn luật (VD: Điều kiện DSCR, điều kiện AML).

4. **Viết `backend/app/services/rag.py` (Xử lý Luồng 1 & AI):**
   * Khởi tạo `OpenAIEmbeddings`.
   * Viết hàm `index_policy_document()`: Cắt text thành các loại Chunk (VD: `POLICY_RULE` 250 tokens), chuyển hóa vector, ghi vào Postgres.
   * Viết hàm `search_policies()`: Dùng câu lệnh SQL `ORDER BY embedding <=> :q_vec` kết hợp `WHERE metadata_->>'department' = :dept` để tìm kiếm.

5. **Viết script nạp dữ liệu (Seeding):**
   * Tạo `backend/scripts/seed_rag.py` gọi hàm `index_policy_document()` chạy lặp qua thư mục `mock_policies/` để mồi sẵn dữ liệu vào Database trước khi lập trình AI Agents.
