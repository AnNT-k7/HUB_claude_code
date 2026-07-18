"""RAG indexing and pgvector similarity search for policy documents."""

from functools import lru_cache
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import PolicyEmbedding
from app.services.embeddings import get_configured_embeddings


settings = get_settings()
DATABASE_EMBEDDING_DIMENSIONS = 1024


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    """Build the configured embedding client compatible with Vector(1024)."""
    if settings.embedding_dimensions != DATABASE_EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"EMBEDDING_DIMENSIONS={settings.embedding_dimensions} is incompatible "
            f"with the database Vector({DATABASE_EMBEDDING_DIMENSIONS}) column."
        )
    return get_configured_embeddings()


def _validate_vector(vector: list[float]) -> None:
    if len(vector) != DATABASE_EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Embedding has {len(vector)} dimensions; "
            f"expected {DATABASE_EMBEDDING_DIMENSIONS}."
        )


def split_text_into_chunks(document_text: str, chunk_type: str) -> list[str]:
    """Split raw text while preferring Vietnamese legal boundaries."""
    if chunk_type == "POLICY_RULE":
        chunk_size, chunk_overlap = 350, 50
    elif chunk_type == "CASE_EVIDENCE":
        chunk_size, chunk_overlap = 500, 100
    else:
        chunk_size, chunk_overlap = 400, 50

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\nĐiều", "\nKhoản", ". ", "\n", " "],
    )
    return splitter.split_text(document_text)


def index_policy_document(
    db: Session,
    document_text: str,
    document_name: str,
    department_tag: str,
    chunk_type: str = "POLICY_RULE",
) -> None:
    """Split a raw document, embed it in one API batch, and store it."""
    chunks = [
        chunk.strip()
        for chunk in split_text_into_chunks(document_text, chunk_type)
        if chunk.strip()
    ]
    if not chunks:
        return

    vectors = get_embeddings().embed_documents(chunks)
    for vector in vectors:
        _validate_vector(vector)

    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        db.add(
            PolicyEmbedding(
                content_chunk=chunk,
                embedding=vector,
                metadata_={
                    "department": department_tag.upper(),
                    "chunk_type": chunk_type,
                    "document_name": document_name,
                    "chunk_index": index,
                    "embedding_provider": settings.embedding_provider,
                    "embedding_model": settings.embedding_model,
                    "embedding_dimensions": settings.embedding_dimensions,
                },
            )
        )
    db.commit()


def search_policies(
    db: Session,
    query_text: str,
    department_filter: str,
    top_k: int = 5,
    chunk_type: str = "POLICY_RULE",
) -> list[dict[str, Any]]:
    """Search similar policy chunks with hard department/type filters."""
    query_vector = get_embeddings().embed_query(query_text)
    _validate_vector(query_vector)

    # metadata_ is the Python attribute; the physical PostgreSQL column is metadata.
    sql = text(
        """
        SELECT content_chunk, metadata
        FROM policy_embeddings
        WHERE metadata->>'department' = :dept
          AND metadata->>'chunk_type' = :c_type
        ORDER BY embedding <=> CAST(:q_vec AS vector)
        LIMIT :k
        """
    )
    vector_string = f"[{','.join(map(str, query_vector))}]"
    results = db.execute(
        sql,
        {
            "dept": department_filter.upper(),
            "c_type": chunk_type,
            "q_vec": vector_string,
            "k": top_k,
        },
    ).fetchall()
    return [{"content": row[0], "citation": row[1]} for row in results]
