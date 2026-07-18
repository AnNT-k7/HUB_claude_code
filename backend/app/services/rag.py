"""
RAG Service — Handles indexing and querying of policy documents.
Provides 5-chunk taxonomy processing and pgvector similarity search.
"""
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.db.models import PolicyEmbedding
from app.config import get_settings

settings = get_settings()

# We initialize the embeddings model. It requires OPENAI_API_KEY.
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small", 
    api_key=settings.openai_api_key
)

def split_text_into_chunks(text: str, chunk_type: str) -> List[str]:
    """
    Split document text into chunks based on taxonomy rules.
    """
    if chunk_type == "POLICY_RULE":
        # Policy rules should be smaller and not break mid-clause
        chunk_size = 350
        chunk_overlap = 50
    elif chunk_type == "CASE_EVIDENCE":
        chunk_size = 500
        chunk_overlap = 100
    else:
        chunk_size = 400
        chunk_overlap = 50

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\nĐiều", "\nKhoản", ". ", "\n", " "]
    )
    return splitter.split_text(text)

def index_policy_document(
    db: Session, 
    document_text: str, 
    document_name: str, 
    department_tag: str, 
    chunk_type: str = "POLICY_RULE"
):
    """
    Process raw text, generate embeddings, and store them into pgvector.
    """
    chunks = split_text_into_chunks(document_text, chunk_type)
    
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
            
        vector = embeddings.embed_query(chunk)
        
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

def search_policies(
    db: Session, 
    query_text: str, 
    department_filter: str, 
    top_k: int = 5,
    chunk_type: str = "POLICY_RULE"
) -> List[Dict[str, Any]]:
    """
    Search for semantically similar policy chunks with hard metadata filtering.
    """
    query_vector = embeddings.embed_query(query_text)
    
    # pgvector cosine distance operator is <=>
    sql = text("""
        SELECT content, metadata_
        FROM policy_embeddings
        WHERE metadata_->>'department' = :dept
          AND metadata_->>'chunk_type' = :c_type
        ORDER BY embedding <=> :q_vec
        LIMIT :k
    """)
    
    # Needs to be formatted as string for pgvector parsing
    vector_str = f"[{','.join(map(str, query_vector))}]"
    
    results = db.execute(
        sql, 
        {
            "dept": department_filter, 
            "c_type": chunk_type,
            "q_vec": vector_str, 
            "k": top_k
        }
    ).fetchall()
    
    return [
        {"content": row[0], "citation": row[1]} 
        for row in results
    ]
