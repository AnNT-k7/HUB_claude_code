import os
import sys
import json
from typing import List, Optional
from pydantic import BaseModel, Field

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate

# =====================================================================
# 1. Định nghĩa các cấu trúc JSON (Pydantic Models) theo RAG-ARCHITECTURE
# =====================================================================

class PolicyRule(BaseModel):
    """Cấu trúc cho loại POLICY_RULE (Chính sách tín dụng, Rủi ro)"""
    chunk_type: str = Field(default="POLICY_RULE")
    rule: str = Field(description="Tên quy định, ví dụ: DSCR tối thiểu")
    condition: str = Field(description="Điều kiện áp dụng, ví dụ: Khoản vay trung dài hạn")
    threshold: str = Field(description="Ngưỡng quy định, ví dụ: DSCR >= 1.2")
    exception: Optional[str] = Field(description="Các ngoại lệ (nếu có)")
    consequence: str = Field(description="Hành động xử lý nếu không đáp ứng")

class LegalClause(BaseModel):
    """Cấu trúc cho loại LEGAL_CLAUSE (Hợp đồng, Điều lệ, Pháp lý)"""
    chunk_type: str = Field(default="LEGAL_CLAUSE")
    clause_id: str = Field(description="Số Điều/Khoản, ví dụ: Điều 15")
    title: str = Field(description="Tiêu đề của điều khoản")
    content: str = Field(description="Nội dung chính của quyền hoặc nghĩa vụ")
    cross_references: List[str] = Field(description="Các tham chiếu chéo đến điều khoản/luật khác (nếu có)")

class ProcessStep(BaseModel):
    """Cấu trúc cho loại PROCESS_STEP (Quy trình vận hành)"""
    chunk_type: str = Field(default="PROCESS_STEP")
    step: str = Field(description="Tên bước thực hiện, ví dụ: Kiểm tra điều kiện giải ngân")
    input: str = Field(description="Đầu vào của bước, ví dụ: Hồ sơ đã phê duyệt")
    checks: List[str] = Field(description="Các yếu tố cần kiểm tra")
    output: str = Field(description="Kết quả đầu ra của bước")
    owner: str = Field(description="Người/Phòng ban chịu trách nhiệm (vd: Banking Operations)")
    exception: Optional[str] = Field(description="Xử lý khi có ngoại lệ, sai sót")

# Wrapper models to allow extracting MULTIPLE chunks from a single text block
class ExtractedPolicyRules(BaseModel):
    items: List[PolicyRule]

class ExtractedLegalClauses(BaseModel):
    items: List[LegalClause]

class ExtractedProcessSteps(BaseModel):
    items: List[ProcessStep]

# =====================================================================
# 2. Setup LLM Parser
# =====================================================================

def get_llm():
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)

def extract_chunks(text: str, chunk_type: str):
    """
    Sử dụng LLM để đọc text thô và parse ra mảng JSON theo đúng định dạng.
    """
    llm = get_llm()
    if chunk_type == "POLICY_RULE":
        schema = ExtractedPolicyRules
        sys_msg = "Bạn là chuyên gia phân tích rủi ro. Hãy trích xuất các quy tắc chính sách từ văn bản sau và format thành mảng JSON PolicyRule. Bỏ qua các đoạn không chứa quy tắc."
    elif chunk_type == "LEGAL_CLAUSE":
        schema = ExtractedLegalClauses
        sys_msg = "Bạn là chuyên gia pháp lý. Hãy trích xuất từng điều khoản từ văn bản sau thành mảng JSON LegalClause. Phải giữ nguyên ngữ nghĩa cốt lõi."
    elif chunk_type == "PROCESS_STEP":
        schema = ExtractedProcessSteps
        sys_msg = "Bạn là chuyên gia vận hành ngân hàng. Hãy trích xuất các bước quy trình từ văn bản sau thành mảng JSON ProcessStep."
    else:
        return []

    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_msg),
        ("human", "{text}")
    ])
    
    # Use with_structured_output for guaranteed JSON schema matching
    chain = prompt | llm.with_structured_output(schema)
    
    try:
        result = chain.invoke({"text": text})
        return [item.model_dump() for item in result.items]
    except Exception as e:
        print(f"Error parsing chunk: {e}")
        return []

# =====================================================================
# 3. Main Test Function
# =====================================================================

def run_test():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "mock_policies"))
    
    # 3 files test đại diện
    test_files = [
        {"path": os.path.join(base_dir, "legal", "Dieu-le-SHB2017.md"), "type": "LEGAL_CLAUSE"},
        {"path": os.path.join(base_dir, "operations", "Niêm-yết-Quy-định-tiền-gửi-tiết-kiệm.md"), "type": "PROCESS_STEP"},
        {"path": os.path.join(base_dir, "risk", "CONG-BO-TY-LE-AN-TOAN-VON-31-12-2023.md"), "type": "POLICY_RULE"}
    ]
    
    output_results = {}
    
    # Split text ra tầm 1000 tokens trước khi ném vào LLM để tránh quá tải
    pre_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200, separators=["\nĐiều", "\nChương", "\n\n"])

    for file_info in test_files:
        fpath = file_info["path"]
        ctype = file_info["type"]
        
        print(f"\n--- Processing: {os.path.basename(fpath)} (Type: {ctype}) ---")
        if not os.path.exists(fpath):
            print(f"File not found: {fpath}")
            continue
            
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Lấy 1 khúc đầu (khoảng 3000 ký tự) để test thôi, tránh tốn tiền LLM và chờ lâu
        test_block = content[:3000]
        segments = pre_splitter.split_text(test_block)
        
        file_extracted_json = []
        for i, segment in enumerate(segments[:2]): # Test max 2 segments per file
            print(f"  -> Extracting JSON from segment {i+1}...")
            json_list = extract_chunks(segment, ctype)
            file_extracted_json.extend(json_list)
            
        output_results[os.path.basename(fpath)] = file_extracted_json

    # Ghi ra file JSON kết quả
    out_file = os.path.join(os.path.dirname(__file__), "test_chunk_output.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_results, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ Đã trích xuất xong! Kết quả lưu tại: {out_file}")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: Chưa có OPENAI_API_KEY trong môi trường. Vui lòng thêm vào file .env")
        sys.exit(1)
    run_test()
