import os
import sys
import json
import random
from typing import List, Dict, Any

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.db.models import Base, PolicyEmbedding
from app.config import get_settings

settings = get_settings()

CHUNKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed_chunks"))

def get_embedding_vector(text_content: str, use_mock: bool = False) -> List[float]:
    """
    Generate 1536-dimensional vector embedding for text (Standard OpenAI text-embedding-3-small dim).
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    if not use_mock and api_key and not api_key.startswith("sk--"):
        try:
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
            return embeddings.embed_query(text_content)
        except Exception as e:
            print(f"  [WARNING] Failed to call OpenAI API ({e}). Falling back to 1536-dim vector generator.")

    # Generate 1536-dim normalized vector matching Vector(1536) schema
    random.seed(hash(text_content) % 10000000)
    vec = [random.uniform(-1, 1) for _ in range(1536)]
    norm = sum(x*x for x in vec) ** 0.5
    return [x / norm for x in vec]

def embed_and_store_chunks(use_mock_embedding: bool = False):
    print("Initializing Database Tables & Vector Extension...")
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[ERROR] Could not connect to PostgreSQL Database: {e}")
        print("Vui long khoi dong PostgreSQL Database (vd: docker-compose up db -d) truoc khi chay script.")
        return

    db: Session = SessionLocal()
    
    folder_department_map = {
        "legal_chunks.json": "LEGAL",
        "operations_chunks.json": "OPERATIONS",
        "risk_chunks.json": "RISK"
    }

    total_embedded = 0

    try:
        for json_file, department in folder_department_map.items():
            file_path = os.path.join(CHUNKS_DIR, json_file)
            if not os.path.exists(file_path):
                print(f"Skipping {json_file} (File not found)")
                continue

            print(f"\nProcessing {json_file} for Department: {department}...")
            with open(file_path, "r", encoding="utf-8") as f:
                chunks: List[Dict[str, Any]] = json.load(f)

            print(f"Found {len(chunks)} chunks. Generating embeddings & inserting...")
            
            batch_records = []
            for idx, chunk_data in enumerate(chunks):
                content_text = json.dumps(chunk_data, ensure_ascii=False)
                vector = get_embedding_vector(content_text, use_mock=use_mock_embedding)

                record = PolicyEmbedding(
                    content_chunk=content_text,
                    embedding=vector,
                    metadata_={
                        "department": department,
                        "chunk_type": chunk_data.get("chunk_type", "POLICY_RULE"),
                        "document_name": chunk_data.get("document_name", ""),
                        "clause_id": chunk_data.get("clause_id", ""),
                        "step": chunk_data.get("step", ""),
                        "rule": chunk_data.get("rule", "")
                    }
                )
                batch_records.append(record)

                if len(batch_records) >= 100:
                    db.bulk_save_objects(batch_records)
                    db.commit()
                    batch_records = []
                    print(f"  -> Embedded & saved {idx + 1}/{len(chunks)} chunks...")

            if batch_records:
                db.bulk_save_objects(batch_records)
                db.commit()

            print(f"[SUCCESS] Completed embedding {len(chunks)} chunks for {department}!")
            total_embedded += len(chunks)

        print(f"\nSUCCESS! Embedded total {total_embedded} chunks into PostgreSQL (pgvector).")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] An error occurred during embedding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    use_mock = "--mock" in sys.argv
    embed_and_store_chunks(use_mock_embedding=use_mock)
