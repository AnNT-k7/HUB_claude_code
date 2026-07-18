import os
import sys
import re
import json
from typing import List, Dict, Any

MOCK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "mock_policies"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed_chunks"))

os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_legal_file(filepath: str) -> List[Dict[str, Any]]:
    """
    Parse Legal Markdown documents into LEGAL_CLAUSE JSON chunks.
    Splits by 'Điều X' or heading blocks.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    filename = os.path.basename(filepath)
    chunks = []
    
    # Pattern to find articles (Điều 1, Điều 2...) or major sections
    pattern = r'(?=(\n|^)(?:#+\s*|Điều\s+\d+[\.\:]?\s*))'
    blocks = [b.strip() for b in re.split(pattern, text) if b and len(b.strip()) > 30]

    for idx, block in enumerate(blocks):
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue
            
        first_line = lines[0]
        # Extract clause_id if present
        clause_match = re.search(r'(Điều\s+\d+[\.\:]?|Chương\s+[IVXLCDM\d]+)', first_line, re.IGNORECASE)
        clause_id = clause_match.group(0) if clause_match else f"Khoản {idx + 1}"
        
        title = first_line.replace("#", "").strip()
        body = "\n".join(lines[1:]) if len(lines) > 1 else first_line

        # Extract cross references (e.g. Luật..., Thông tư..., Điều...)
        refs = re.findall(r'(Luật\s+[\w\s]+|Thông tư\s+[\d\/\-\w]+|Nghị định\s+[\d\/\-\w]+|Điều\s+\d+)', block)
        unique_refs = list(set([r.strip() for r in refs if len(r.strip()) > 3]))

        chunks.append({
            "chunk_type": "LEGAL_CLAUSE",
            "document_name": filename,
            "clause_id": clause_id,
            "title": title,
            "content": body[:1000],  # Keep reasonable size
            "cross_references": unique_refs[:5]
        })

    return chunks

def parse_operations_file(filepath: str) -> List[Dict[str, Any]]:
    """
    Parse Operations Markdown documents into PROCESS_STEP JSON chunks.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    filename = os.path.basename(filepath)
    chunks = []

    # Split by numbered items or headings (1., 2., Bước 1, ##)
    blocks = re.split(r'\n(?=\d+[\.\)]\s*|\#+\s*|Bước\s+\d+)', text)

    for idx, block in enumerate(blocks):
        block = block.strip()
        if len(block) < 30:
            continue

        lines = [line.strip() for line in block.split('\n') if line.strip()]
        step_title = lines[0].replace("#", "").strip()
        
        # Extract bullet points as checks
        checks = [l.lstrip('-*•a)b)c)d)').strip() for l in lines[1:] if re.match(r'^\s*[-*•a-z\)]', l)]
        if not checks:
            checks = [lines[1]] if len(lines) > 1 else [step_title]

        chunks.append({
            "chunk_type": "PROCESS_STEP",
            "document_name": filename,
            "step": step_title,
            "input": "Hồ sơ / Giấy tờ liên quan theo quy định",
            "checks": checks[:5],
            "output": "Hoàn tất kiểm tra / Thực hiện bước nghiệp vụ",
            "owner": "Banking Operations Department",
            "exception": "Dừng giải ngân / từ chối nếu không đáp ứng điều kiện"
        })

    return chunks

def parse_risk_file(filepath: str) -> List[Dict[str, Any]]:
    """
    Parse Risk Management Markdown documents into POLICY_RULE JSON chunks.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    filename = os.path.basename(filepath)
    chunks = []

    blocks = re.split(r'\n(?=\#+\s*|\d+[\.\)]\s*|Điều\s+\d+)', text)

    for idx, block in enumerate(blocks):
        block = block.strip()
        if len(block) < 30:
            continue

        lines = [line.strip() for line in block.split('\n') if line.strip()]
        rule_title = lines[0].replace("#", "").strip()

        # Find potential percentage/ratio thresholds (e.g., 8%, 100%, 1.25)
        thresholds = re.findall(r'(\d+(?:\,\d+)?\s*\%|\d+(?:\,\d+)?\s*lần|>=?\s*\d+[\.\,]?\d*)', block)
        threshold_str = ", ".join(set(thresholds)) if thresholds else "Theo quy định hạn mức rủi ro hiện hành"

        chunks.append({
            "chunk_type": "POLICY_RULE",
            "document_name": filename,
            "rule": rule_title,
            "condition": "Áp dụng đối với toàn bộ hoạt động quản trị rủi ro & tỷ lệ an toàn",
            "threshold": threshold_str,
            "exception": "Trường hợp có chấp thuận/ngoại lệ từ Hội đồng Quản trị hoặc Ngân hàng Nhà nước",
            "consequence": "Phải báo cáo Khối Quản trị Rủi ro và thực hiện biện pháp khắc phục hạn mức"
        })

    return chunks

def main():
    folder_mapping = {
        "legal": parse_legal_file,
        "operations": parse_operations_file,
        "risk": parse_risk_file
    }

    total_chunks = 0

    for folder_name, parser_fn in folder_mapping.items():
        folder_path = os.path.join(MOCK_DIR, folder_name)
        if not os.path.exists(folder_path):
            continue

        folder_chunks = []
        md_files = [f for f in os.listdir(folder_path) if f.endswith(".md") and not f.startswith("README")]
        
        print(f"Processing folder '{folder_name}' ({len(md_files)} .md files)...")

        for fname in md_files:
            fpath = os.path.join(folder_path, fname)
            try:
                extracted = parser_fn(fpath)
                folder_chunks.extend(extracted)
            except Exception as e:
                print(f"  [ERROR] Failed to parse {fname}: {e}")

        output_file = os.path.join(OUTPUT_DIR, f"{folder_name}_chunks.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(folder_chunks, f, ensure_ascii=False, indent=2)

        print(f"  -> Successfully generated {len(folder_chunks)} chunks for '{folder_name}' saved to: {output_file}")
        total_chunks += len(folder_chunks)

    print(f"\nDONE! Total {total_chunks} structured JSON chunks generated across legal, operations, and risk.")

if __name__ == "__main__":
    main()
