import os
import sys

# Add the backend directory to sys.path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.services.rag import index_policy_document

MOCK_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "mock_policies"))

def seed_database():
    print(f"Starting RAG Seeding process from: {MOCK_DATA_DIR}")
    db = SessionLocal()
    
    try:
        for department_tag in os.listdir(MOCK_DATA_DIR):
            dept_path = os.path.join(MOCK_DATA_DIR, department_tag)
            
            if os.path.isdir(dept_path):
                print(f"\nProcessing department: {department_tag.upper()}")
                
                for filename in os.listdir(dept_path):
                    if filename.endswith(".txt") or filename.endswith(".md"):
                        # Skip READMEs if needed, but let's just index everything for demo
                        if "README" in filename:
                            continue
                            
                        file_path = os.path.join(dept_path, filename)
                        print(f"  - Indexing: {filename}")
                        
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            
                        index_policy_document(
                            db=db,
                            document_text=content,
                            document_name=filename,
                            department_tag=department_tag.upper(),
                            chunk_type="POLICY_RULE"
                        )
                        
        print("\nSeeding completed successfully!")
        
    except Exception as e:
        print(f"Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
