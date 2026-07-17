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

## 2. Bản đồ File & Folder chịu trách nhiệm (Code Mapping)

| Giai đoạn | File / Folder chịu trách nhiệm | Mô tả Logic & Chức năng |
| :--- | :--- | :--- |
| **1. INDEX** | `backend/app/services/rag.py` <br> `backend/app/db/models.py` | • Đọc tài liệu quy chế tín dụng, KYC, LTV từ file tĩnh/S3.<br>• Cắt đoạn (**Chunking**) từ 500-1000 từ.<br>• Chuyển đổi thành vector 1536 chiều qua OpenAI Embeddings.<br>• Ghi vào bảng `policy_embeddings` trên PostgreSQL (`pgvector`) kèm nhãn `metadata_={"department": "CREDIT"}`. |
| **2. QUERY** | `backend/app/services/rag.py` <br> *(Được gọi bởi các Specialist Agents)* | • Nhận `query` và `department` từ Specialist Agent.<br>• Chuyển `query` thành vector và chạy tìm kiếm **Cosine Similarity (`<=>`)**.<br>• **Luôn khóa cứng bộ lọc:** `WHERE metadata_->>'department' = :department` để tránh sai lệch thông tin phòng ban.<br>• Trả về Top $K$ đoạn chính sách chính xác nhất kèm trang & điều khoản. |
| **3. RENEW PROMPT** | `backend/app/agents/tier2_board/specialists/*.py` <br> `docs/AI-PROMPT-GUIDE.md` | • Trước khi Agent gửi request cho LLM suy luận, tiêm (inject) các đoạn chính sách vừa tìm được vào `System Prompt`.<br>• Buộc LLM phải đối chiếu số liệu của khách hàng với đoạn chính sách này và trích dẫn `exact citation`. |

---

## 3. Chi tiết từng giai đoạn & Code mẫu cho Lập trình viên

### 3.1. Giai đoạn 1: INDEXING (services/rag.py)

Khi nạp tài liệu chính sách mới (ví dụ `Quy_che_tin_dung_2026.pdf`), lập trình viên cần đảm bảo mỗi chunk được lưu kèm đúng `department`:

```python
# Mẫu logic triển khai trong backend/app/services/rag.py

from sqlalchemy.orm import Session
from app.db.models import PolicyEmbedding
# Giả sử dùng LangChain hoặc OpenAI client để tạo vector
# from langchain_openai import OpenAIEmbeddings

def index_policy_document(
    db: Session, 
    document_text: str, 
    document_name: str, 
    department_tag: str  # Ví dụ: "CREDIT", "LEGAL", "COMPLIANCE", "COLLATERAL"
):
    # 1. Chunking (Cắt nhỏ văn bản)
    chunks = split_text_into_chunks(document_text, chunk_size=800, chunk_overlap=100)
    
    # 2. Embedding & Save to DB
    for i, chunk in enumerate(chunks):
        vector = generate_embedding(chunk)  # Trả về list[float] 1536 chiều
        
        record = PolicyEmbedding(
            content=chunk,
            embedding=vector,
            metadata_={
                "department": department_tag,
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
    
    # Sử dụng toán tử Cosine Distance <=> của pgvector kết hợp lọc JSONB metadata
    sql = text("""
        SELECT content, metadata_
        FROM policy_embeddings
        WHERE metadata_->>'department' = :dept
        ORDER BY embedding <=> :q_vec
        LIMIT :k
    """)
    
    results = db.execute(
        sql, 
        {"dept": department_filter, "q_vec": str(query_vector), "k": top_k}
    ).fetchall()
    
    return [
        {"content": row.content, "citation": row.metadata_} 
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

*   **`PolicyEmbedding`:** Bảng ORM trong `db/models.py`, chứa cột `embedding` kiểu `Vector(1536)` của extension `pgvector`.
*   **`metadata_->>'department'`:** Cột JSONB dùng để phân vùng logic (Logical Partitioning), giúp 6 Specialist Agents không bị nhiễu thông tin (noise/hallucination) của nhau dù dùng chung 1 database.
*   **`<=>` (Cosine Distance):** Toán tử tối ưu nhất của `pgvector` để tìm kiếm độ tương đồng giữa câu hỏi và đoạn văn bản chính sách.
*   **Zero-Hallucination:** Quy tắc bắt buộc mọi kết luận của Agent trên `Shared Board` đều phải có trường `evidence` chứa citation lấy ra từ bước Query RAG.
