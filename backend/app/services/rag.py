"""RAG indexing and pgvector similarity search for policy documents."""

from datetime import date
from functools import lru_cache
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import PolicyEmbedding
from app.services.embeddings import get_configured_embeddings


settings = get_settings()
DATABASE_EMBEDDING_DIMENSIONS = 512
ALLOWED_POLICY_CHUNK_TYPES = ("POLICY_RULE", "VERIFICATION_PROCEDURE")


class PolicyQuery(BaseModel):
    """Mandatory scope for every runtime policy retrieval."""

    query_text: str = Field(min_length=3)
    domain: str = "INCOME_VERIFICATION"
    product: str = "UNSECURED_PERSONAL_LOAN"
    chunk_types: list[str] = Field(
        default_factory=lambda: list(ALLOWED_POLICY_CHUNK_TYPES), min_length=1
    )
    as_of_date: date
    top_k: int = Field(default=5, ge=1, le=10)

    def validate_scope(self) -> None:
        if self.domain != "INCOME_VERIFICATION":
            raise ValueError("Policy queries must use the income-verification domain.")
        if self.product != "UNSECURED_PERSONAL_LOAN":
            raise ValueError("Policy queries must use the unsecured personal-loan product.")
        if any(chunk_type not in ALLOWED_POLICY_CHUNK_TYPES for chunk_type in self.chunk_types):
            raise ValueError("Policy query contains an unsupported chunk type.")


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    """Build the configured embedding client compatible with Vector(512)."""
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


def validate_policy_metadata(metadata: dict[str, Any]) -> None:
    """Reject chunks that cannot produce an exact, scoped citation."""

    forbidden_case_fields = {"case_id", "application_id", "customer_name", "transactions"}
    leaked_fields = sorted(forbidden_case_fields.intersection(metadata))
    if leaked_fields:
        raise ValueError(f"Customer/case fields cannot enter the global policy index: {', '.join(leaked_fields)}")
    required = (
        "chunk_id",
        "chunk_type",
        "domain",
        "product",
        "document_name",
        "document_version",
        "page_number",
        "section_id",
        "effective_date",
        "approval_status",
        "content_sha256",
        "source_path",
    )
    missing = [key for key in required if metadata.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Policy metadata missing required fields: {', '.join(missing)}")
    if metadata["chunk_type"] not in ALLOWED_POLICY_CHUNK_TYPES:
        raise ValueError("Only POLICY_RULE and VERIFICATION_PROCEDURE can be indexed.")
    if metadata["domain"] != "INCOME_VERIFICATION":
        raise ValueError("Policy chunk domain is outside the income-verification scope.")
    if metadata["product"] != "UNSECURED_PERSONAL_LOAN":
        raise ValueError("Policy chunk product is outside the unsecured-loan scope.")
    if metadata["approval_status"] != "APPROVED":
        raise ValueError("Only owner-approved policy chunks can enter the global index.")


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


def index_policy_chunks(
    db: Session,
    chunks: list[dict[str, Any]],
    vectors: list[list[float]],
    *,
    embedding_provider: str,
    embedding_model: str,
) -> int:
    """Idempotently index validated corpus chunks by content checksum."""

    if len(chunks) != len(vectors):
        raise ValueError("Chunk/vector count mismatch.")
    from sqlalchemy import select

    inserted = 0
    for chunk, vector in zip(chunks, vectors, strict=True):
        metadata = dict(chunk.get("metadata") or {})
        validate_policy_metadata(metadata)
        _validate_vector(vector)
        checksum = metadata["content_sha256"]
        exists = db.execute(
            select(PolicyEmbedding.id).where(
                PolicyEmbedding.metadata_["content_sha256"].astext == checksum
            )
        ).first()
        if exists:
            continue
        metadata.update(
            {
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "embedding_dimensions": DATABASE_EMBEDDING_DIMENSIONS,
            }
        )
        db.add(
            PolicyEmbedding(
                content_chunk=str(chunk["content_chunk"]),
                embedding=vector,
                metadata_=metadata,
            )
        )
        inserted += 1
    db.commit()
    return inserted


def search_policies(db: Session, query: PolicyQuery) -> list[dict[str, Any]]:
    """Search only effective, approved income-verification policy chunks."""
    query.validate_scope()
    query_vector = get_embeddings().embed_query(query.query_text)
    _validate_vector(query_vector)

    # metadata_ is the Python attribute; the physical PostgreSQL column is metadata.
    sql = text(
        """
        SELECT content_chunk, metadata
        FROM policy_embeddings
        WHERE metadata->>'domain' = :domain
          AND metadata->>'product' = :product
          AND metadata->>'chunk_type' IN ('POLICY_RULE', 'VERIFICATION_PROCEDURE')
          AND metadata->>'approval_status' = 'APPROVED'
          AND (metadata->>'effective_date')::date <= :as_of_date
          AND (
              metadata->>'expiry_date' IS NULL
              OR metadata->>'expiry_date' = ''
              OR (metadata->>'expiry_date')::date >= :as_of_date
          )
        ORDER BY embedding <=> CAST(:q_vec AS vector)
        LIMIT :k
        """
    )
    vector_string = f"[{','.join(map(str, query_vector))}]"
    results = db.execute(
        sql,
        {
            "domain": query.domain,
            "product": query.product,
            "as_of_date": query.as_of_date,
            "q_vec": vector_string,
            "k": query.top_k,
        },
    ).fetchall()
    return [{"content": row[0], "citation": row[1]} for row in results]
