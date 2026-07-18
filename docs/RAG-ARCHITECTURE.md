# Hướng dẫn Kiến trúc RAG & Quy trình Index -> Query -> Renew Prompt

**Dự án:** Digital Expert Agents — Hệ thống Đánh giá Sơ bộ Hồ sơ Tín dụng Doanh nghiệp  
**Đối tượng sử dụng:** Lập trình viên, AI Engineering Team, System Architects  
**Mục đích:** Tra cứu nhanh logic xử lý, luồng dữ liệu và vị trí file/folder cho hệ thống Retrieval-Augmented Generation (RAG) nhằm tuân thủ nguyên tắc **Zero-Hallucination** (Không bịa đặt thông tin) và **Department Isolation** (Cô lập theo chuyên môn phòng ban).

---

## 1. Tổng quan Luồng RAG (RAG Pipeline Overview)

Trong kiến trúc Multi-Agent của Digital Expert Agents, **RAG không phải là một module chạy độc lập** mà là hệ thống bộ nhớ chính sách được nhúng trực tiếp vào vòng đời suy luận của các **Specialist Agents (Tầng 2)**.

Toàn bộ quy trình RAG được chia làm 3 giai đoạn chính:

```
[Tài liệu Chính sách SHB]
         │
         ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ 1. INDEXING (Nạp & Nhúng vector vào PostgreSQL pgvector)     │
 │    File chịu trách nhiệm: backend/app/services/rag.py        │
 │    Bảng dữ liệu: policy_embeddings (trong db/models.py)      │
 └──────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ 2. QUERYING (Tìm kiếm ngữ nghĩa + Lọc cứng theo Phòng ban)  │
 │    Hàm xử lý: search_policies() trong services/rag.py        │
 │    Được gọi từ: backend/app/agents/tier2_board/specialists/  │
 └──────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ 3. RENEW PROMPT / AUGMENTATION (Tiêm RAG vào System Prompt) │
 │    File xử lý: specialist agents (credit.py, legal.py...)    │
 │    Quy chuẩn Prompt: docs/AI-PROMPT-GUIDE.md                 │
 └──────────────────────────────────────────────────────────────┘
```

---

## 2. Chuẩn hóa Phân loại 5 Loại Chunk (Chunking Taxonomy & Specifications)

Để đảm bảo tính chính xác tuyệt đối, không bị trôi ngữ cảnh hoặc chia cắt điều khoản, dữ liệu trong hệ thống RAG bắt buộc phải được phân loại thành **5 loại chunk chuẩn** (`chunk_type`). Mỗi loại có chiến lược cắt (chunking strategy), kích thước (token size) và cấu trúc dữ liệu riêng biệt:

### A. `POLICY_RULE` (Chính sách & Quy định tín dụng)
*   **Mục đích:** Dùng cho quy định, chính sách hạn mức, khẩu vị rủi ro, pháp luật ngân hàng.
*   **Quy chuẩn cấu trúc:** Một chunk phải chứa trọn bộ 4 thành phần: `Điều kiện + Ngưỡng + Ngoại lệ + Hành động xử lý`.
*   **Kích thước chuẩn:** `150–350 tokens`, **tuyệt đối không cắt giữa chừng Điều/Khoản**.
*   **Ví dụ JSON Metadata / Payload:**
    ```json
    {
      "chunk_type": "POLICY_RULE",
      "rule": "DSCR tối thiểu",
      "condition": "Khoản vay trung dài hạn",
      "threshold": "DSCR >= 1.2",
      "exception": "Có phê duyệt cấp cao hơn",
      "consequence": "Không đáp ứng thì từ chối hoặc bổ sung nguồn trả nợ"
    }
    ```

### B. `CASE_EVIDENCE` (Hồ sơ chứng cứ khách hàng)
*   **Mục đích:** Dùng cho hồ sơ vay, phương án kinh doanh, biên bản làm việc, báo cáo thẩm định thực tế.
*   **Quy chuẩn cấu trúc:** Mỗi chunk tập trung trọn vẹn vào **một chủ đề duy nhất**:
    *   Thông tin doanh nghiệp (`Borrower Profile`)
    *   Mục đích vay (`Loan Purpose`)
    *   Nhu cầu vốn (`Capital Requirement`)
    *   Nguồn trả nợ (`Repayment Source`)
    *   Khách hàng/nhà cung cấp chính (`Key Suppliers / Buyers`)
    *   Rủi ro kinh doanh (`Business Risks`)
*   **Kích thước chuẩn:** `300–600 tokens`.

### C. `STRUCTURED_FACT` (Số liệu tài chính định lượng)
*   **Mục đích:** Dùng cho số liệu tài chính, bảng cân đối kế toán, kết quả kinh doanh.
*   **Quy tắc vàng:** **Không nên chỉ embedding toàn bộ bảng tài chính thành text thô.**
*   **Quy chuẩn cấu trúc:** Mỗi record phải được định danh rõ ràng dưới dạng JSON/SQL:
    ```json
    {
      "chunk_type": "STRUCTURED_FACT",
      "metric": "Revenue",
      "period": "2025",
      "value": 250000000000,
      "currency": "VND",
      "source_page": 12
    }
    ```
*   **Chiến lược Hybrid Storage:** Nên lưu định dạng có cấu trúc (SQL/JSONB) để query chính xác, **đồng thời tạo thêm câu text mô tả tự nhiên** để phục vụ vector similarity search:
    👉 *Ví dụ câu text tìm kiếm:* `"Doanh thu năm 2025 là 250 tỷ VND, tăng 18% so với 2024."*
*   **⚠️ NGUYÊN TẮC ZERO-HALLUCINATION:** Các chỉ số tài chính phái sinh phức tạp như **DSCR, EBITDA, Leverage (D/E)** phải được **công cụ (Python Tool/Engine) tính toán trực tiếp từ số liệu thô `STRUCTURED_FACT`**. **Tuyệt đối không để LLM tự tính nhẩm từ nhiều chunk rời rạc!**

### D. `LEGAL_CLAUSE` (Điều khoản pháp lý & Hợp đồng)
*   **Mục đích:** Dùng cho hợp đồng tín dụng, điều lệ công ty, hồ sơ pháp lý, đăng ký giao dịch bảo đảm.
*   **Quy chuẩn cấu trúc:** Một chunk tương ứng trọn vẹn với:
    *   Một điều khoản (`Single Clause`)
    *   Một quyền hoặc nghĩa vụ (`Right or Obligation`)
    *   Một điều kiện chấm dứt (`Termination Condition`)
    *   Một nội dung về bảo lãnh (`Guarantee Term`)
    *   Một giới hạn chuyển nhượng (`Transfer Restriction`)
*   **Yêu cầu bắt buộc:** Phải giữ nguyên số điều, tên các bên liên quan, ngày hiệu lực và các tham chiếu chéo (`Cross-references`).

### E. `PROCESS_STEP` (Quy trình vận hành & Giải ngân)
*   **Mục đích:** Dùng cho quy trình vận hành (SOP), hướng dẫn kiểm tra trước giải ngân của `Banking Operations Department`.
*   **Quy chuẩn cấu trúc:** Một chunk phải có dạng cấu trúc hành động rõ ràng:
    ```json
    {
      "chunk_type": "PROCESS_STEP",
      "step": "Kiểm tra điều kiện giải ngân",
      "input": "Hồ sơ đã phê duyệt",
      "checks": ["Hợp đồng đã ký", "Tài sản đã đăng ký bảo đảm"],
      "output": "Cho phép giải ngân",
      "owner": "Banking Operations",
      "exception": "Thiếu chứng từ thì dừng giải ngân"
    }
    ```

---

## 3. Bản đồ File & Folder chịu trách nhiệm (Code Mapping)

| Giai đoạn | File / Folder chịu trách nhiệm | Mô tả Logic & Chức năng |
| :--- | :--- | :--- |
| **1. INDEX** | `backend/app/services/rag.py` <br> `backend/app/db/models.py` | • Phân loại văn bản vào đúng 1 trong 5 `chunk_type` chuẩn (`POLICY_RULE`, `CASE_EVIDENCE`, `STRUCTURED_FACT`, `LEGAL_CLAUSE`, `PROCESS_STEP`).<br>• Cắt đoạn theo token size chuẩn của từng loại.<br>• Chuyển đổi bằng FPT `Vietnamese_Embedding` thành vector 1024 chiều và lưu vào `policy_embeddings` kèm JSONB `metadata` (`metadata_` là tên thuộc tính ORM). |
| **2. QUERY** | `backend/app/services/rag.py` <br> *(Được gọi bởi các Specialist Agents)* | • Nhận `query`, `department` và tùy chọn `chunk_type` từ Specialist Agent.<br>• Chuyển `query` thành vector và chạy tìm kiếm **Cosine Similarity (`<=>`)**.<br>• **Khóa cứng bộ lọc:** `WHERE metadata->>'department' = :dept AND metadata->>'chunk_type' = :c_type`.<br>• Trả về Top $K$ đoạn chính xác nhất. |
| **3. RENEW PROMPT** | `backend/app/agents/tier2_board/specialists/*.py` <br> `docs/AI-PROMPT-GUIDE.md` | • Trước khi Agent gửi request cho LLM suy luận, tiêm (inject) các đoạn chính sách vừa tìm được vào `System Prompt`.<br>• Buộc LLM phải đối chiếu số liệu của khách hàng với đoạn chính sách này và trích dẫn `exact citation`. |

---

## 4. Chi tiết từng giai đoạn & Code mẫu cho Lập trình viên

### 4.1. Giai đoạn 1: INDEXING với phân loại Chunk Type (services/rag.py)

Khi nạp tài liệu chính sách mới, lập trình viên bắt buộc phải gán nhãn `chunk_type` và `department`:

```python
# Mẫu logic triển khai trong backend/app/services/rag.py

from sqlalchemy.orm import Session
from app.db.models import PolicyEmbedding
# Local model được khởi tạo tập trung trong app/services/embeddings.py

def index_policy_document(
    db: Session, 
    document_text: str, 
    document_name: str, 
    department_tag: str,  # "CREDIT", "LEGAL", "COMPLIANCE", "COLLATERAL", "OPERATIONS"
    chunk_type: str       # "POLICY_RULE", "CASE_EVIDENCE", "STRUCTURED_FACT", "LEGAL_CLAUSE", "PROCESS_STEP"
):
    # 1. Chunking tùy theo loại chunk_type (ví dụ POLICY_RULE dùng 200 tokens, CASE_EVIDENCE dùng 500 tokens)
    chunk_size = 250 if chunk_type == "POLICY_RULE" else 500
    chunks = split_text_into_chunks(document_text, chunk_size=chunk_size, chunk_overlap=50)
    
    # 2. Embedding & Save to DB
    for i, chunk in enumerate(chunks):
        vector = generate_embedding(chunk)  # Trả về list[float] 1024 chiều
        
        record = PolicyEmbedding(
            content=chunk,
            embedding=vector,
            metadata_={
                "department": department_tag,
                "chunk_type": chunk_type,
                "document_name": document_name,
                "chunk_index": i
            }
        )
        db.add(record)
    db.commit()
```

---

### 3.2. Giai đoạn 2: QUERYING với cô lập phòng ban (services/rag.py)

**Nguyên tắc sống còn:** Không bao giờ cho phép một Specialist Agent search trên toàn bộ bảng `policy_embeddings` mà không có bộ lọc `department`.

```python
# Mẫu logic tìm kiếm RAG trong backend/app/services/rag.py

from sqlalchemy import text
from typing import List, Dict, Any

def search_policies(
    db: Session, 
    query_text: str, 
    department_filter: str, 
    top_k: int = 5
) -> List[Dict[str, Any]]:
    query_vector = generate_embedding(query_text)
    vector_string = f"[{','.join(map(str, query_vector))}]"
    
    # Sử dụng toán tử Cosine Distance <=> của pgvector kết hợp lọc JSONB metadata
    sql = text("""
        SELECT content_chunk, metadata
        FROM policy_embeddings
        WHERE metadata->>'department' = :dept
        ORDER BY embedding <=> CAST(:q_vec AS vector)
        LIMIT :k
    """)
    
    results = db.execute(
        sql, 
        {"dept": department_filter, "q_vec": vector_string, "k": top_k}
    ).fetchall()
    
    return [
        {"content": row.content_chunk, "citation": row.metadata}
        for row in results
    ]
```

---

### 3.3. Giai đoạn 3: RENEW PROMPT / AUGMENTATION (specialists/*.py)

Khi viết code cho một Specialist Agent (ví dụ: `Credit Agent` tại `backend/app/agents/tier2_board/specialists/credit.py`), trước khi gọi LLM, bạn phải gọi `search_policies` và làm mới Prompt:

```python
# Mẫu logic Renew Prompt bên trong Specialist Agent (credit.py)

from app.services.rag import search_policies

def run_credit_agent_analysis(db: Session, case_data: dict) -> dict:
    # 1. Thực hiện Query lấy chính sách liên quan đến chỉ số tài chính đang xét
    rag_results = search_policies(
        db=db,
        query="Ngưỡng tỷ lệ bao phủ nợ DSCR và tỷ lệ nợ trên vốn chủ sở hữu D/E cho phép",
        department_filter="CREDIT",
        top_k=3
    )
    
    # 2. Định dạng chuỗi chính sách để tiêm vào Prompt
    evidence_block = "\n---\n".join([
        f"[Nguồn: {item['citation'].get('document_name')}] {item['content']}"
        for item in rag_results
    ])
    
    # 3. RENEW PROMPT (Tiêm RAG Evidence vào System Prompt)
    renewed_system_prompt = f"""
    Bạn là Chuyên gia Tín dụng (Credit Agent) thuộc Ngân hàng SHB.
    
    === CHÍNH SÁCH VÀ NGƯỠNG AN TOÀN BẮT BUỘC (RAG EVIDENCE) ===
    {evidence_block}
    ============================================================
    
    Hồ sơ khách hàng cần đánh giá:
    - DSCR tính toán: {case_data['calculated_dscr']}
    - D/E tính toán: {case_data['calculated_leverage']}
    
    YÊU CẦU:
    1. Đối chiếu chỉ số của khách hàng với chính sách trong RAG EVIDENCE.
    2. Nếu vi phạm ngưỡng, đánh dấu rủi ro (risk_flags) và ghi rõ lý do.
    3. BẮT BUỘC trích dẫn nguyên văn (exact citation) tên tài liệu chính sách đã dùng.
    """
    
    # 4. Gọi LLM với renewed_system_prompt và trả về CreditAssessment
    # response = llm.invoke(renewed_system_prompt)
    # ...
```

---

## 4. Bảng tra cứu từ khóa & Thuật ngữ nhanh cho Lập trình viên

*   **`PolicyEmbedding`:** Bảng ORM trong `db/models.py`, chứa cột `embedding` kiểu `Vector(1024)` của extension `pgvector`.
*   **`metadata->>'department'`:** Cột JSONB vật lý dùng để phân vùng logic (Logical Partitioning). Trong SQLAlchemy, thuộc tính Python tương ứng có tên `metadata_` để tránh xung đột với `Base.metadata`.
*   **`<=>` (Cosine Distance):** Toán tử tối ưu nhất của `pgvector` để tìm kiếm độ tương đồng giữa câu hỏi và đoạn văn bản chính sách.
*   **Zero-Hallucination:** Quy tắc bắt buộc mọi kết luận của Agent trên `Shared Board` đều phải có trường `evidence` chứa citation lấy ra từ bước Query RAG.

---

## 5. Chạy embedding cho dữ liệu đã chuẩn hóa

Khởi động PostgreSQL/pgvector và kiểm tra đầu vào trước khi tải/chạy model local:

```bash
docker compose up -d postgres
python backend/scripts/embed_processed_chunks.py --dry-run --departments collateral compliance credit
```

Embedding được cấu hình qua FPT AI Marketplace bằng `EMBEDDING_PROVIDER=fpt`, `EMBEDDING_MODEL=Vietnamese_Embedding`, `EMBEDDING_DIMENSIONS=1024` và `FPT_API_KEY`. Runtime query phải dùng chính model FPT này.

```bash
python backend/scripts/embed_processed_chunks.py --provider fpt --departments legal operations risk collateral compliance credit customer_relationship
```

Pipeline chỉ embedding `content_chunk`; citation, payload, checksum và source warning được giữ trong JSONB `metadata`. Index và query bắt buộc dùng cùng model FPT và cùng 1024 chiều. Script nạp theo batch và bỏ qua chunk đã tồn tại theo `content_sha256`, nên có thể chạy lại mà không ghi trùng. Chunk có cảnh báo `EXTERNAL_INSTITUTION_REFERENCE` bị chặn mặc định; chỉ dùng `--allow-external-source` sau khi có phê duyệt rõ ràng của domain owner. `--provider mock` hoặc alias `--mock` chỉ dành cho integration test cục bộ và không được dùng làm dữ liệu tìm kiếm production.
