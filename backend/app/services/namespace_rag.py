"""Shared file-backed retriever for the three demo RAG namespaces."""

from __future__ import annotations

import json
import math
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.services.embeddings import get_configured_embeddings

DEFAULT_CORPUS_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "rag"
    / "three_rag_fpt_corpus.json"
)
REQUIRED_DIMENSIONS = 512


class RagNamespace(StrEnum):
    DOCUMENT_EXTRACTION = "DOCUMENT_EXTRACTION"
    INCOME_ANALYSIS = "INCOME_ANALYSIS"
    POLICY = "POLICY"


class NamespaceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str = Field(min_length=3)
    namespace: RagNamespace
    top_k: int = Field(default=3, ge=1, le=10)
    chunk_types: list[str] = Field(default_factory=list)
    allowed_scopes: list[str] = Field(
        default_factory=lambda: ["REVIEW_ONLY", "DEMO_ONLY", "GLOBAL_POLICY"]
    )


class NamespaceHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    namespace: RagNamespace
    score: float
    content: str
    document_name: str
    page_number: int
    section_id: str
    source_path: str
    chunk_type: str
    indexing_scope: str
    effective_date: date | None = None
    approval_status: str | None = None


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != REQUIRED_DIMENSIONS or len(right) != REQUIRED_DIMENSIONS:
        raise ValueError("RAG vectors must use 512 dimensions.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


def search_namespace(
    query: NamespaceQuery,
    *,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
) -> list[NamespaceHit]:
    """Embed one query and search only its explicitly selected namespace."""

    settings = get_settings()
    if settings.embedding_dimensions != REQUIRED_DIMENSIONS:
        raise RuntimeError("EMBEDDING_DIMENSIONS must be 512 for namespace retrieval.")
    document = json.loads(corpus_path.read_text(encoding="utf-8"))
    namespace_data = document["namespaces"].get(query.namespace.value)
    if namespace_data is None:
        return []
    candidates = []
    for chunk in namespace_data["chunks"]:
        metadata = chunk["metadata"]
        if metadata.get("rag_namespace") != query.namespace.value:
            continue
        if metadata.get("indexing_scope") not in query.allowed_scopes:
            continue
        if query.chunk_types and metadata.get("chunk_type") not in query.chunk_types:
            continue
        vector = chunk.get("embedding")
        if not isinstance(vector, list):
            continue
        candidates.append(chunk)
    if not candidates:
        return []
    query_vector = get_configured_embeddings().embed_query(query.query_text)
    if len(query_vector) != REQUIRED_DIMENSIONS:
        raise ValueError("Query embedding must use 512 dimensions.")
    ranked = sorted(
        (
            (_cosine_similarity(query_vector, chunk["embedding"]), chunk)
            for chunk in candidates
        ),
        key=lambda item: item[0],
        reverse=True,
    )[: query.top_k]
    return [
        NamespaceHit(
            chunk_id=chunk["chunk_id"],
            namespace=query.namespace,
            score=score,
            content=chunk["content_chunk"],
            document_name=str(chunk["metadata"]["document_name"]),
            page_number=int(chunk["metadata"].get("page_number") or 1),
            section_id=str(chunk["metadata"]["section_id"]),
            source_path=str(chunk["metadata"]["source_path"]),
            chunk_type=str(chunk["metadata"]["chunk_type"]),
            indexing_scope=str(chunk["metadata"]["indexing_scope"]),
            effective_date=chunk["metadata"].get("effective_date"),
            approval_status=chunk["metadata"].get("approval_status"),
        )
        for score, chunk in ranked
    ]
