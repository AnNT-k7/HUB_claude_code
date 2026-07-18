"""Embed normalized policy chunks and store them in PostgreSQL/pgvector.

The script supports both the original processed_chunks files and the wrapped
per-department JSON files produced by chunk_departments.py. Provider failures
are never replaced silently with fake vectors. A deterministic mock provider is
available only when it is selected explicitly for local integration tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

EMBEDDING_DIMENSIONS = 1024
DEFAULT_BATCH_SIZE = 16
BLOCKING_SOURCE_WARNING_CODES = {"EXTERNAL_INSTITUTION_REFERENCE"}


@dataclass(frozen=True)
class Dataset:
    key: str
    department: str
    path: Path


DATASETS = {
    "legal": Dataset(
        key="legal",
        department="LEGAL",
        path=BACKEND_DIR / "data" / "processed_chunks" / "legal_chunks.json",
    ),
    "operations": Dataset(
        key="operations",
        department="OPERATIONS",
        path=BACKEND_DIR / "data" / "processed_chunks" / "operations_chunks.json",
    ),
    "risk": Dataset(
        key="risk",
        department="RISK",
        path=BACKEND_DIR / "data" / "processed_chunks" / "risk_chunks.json",
    ),
    "collateral": Dataset(
        key="collateral",
        department="COLLATERAL",
        path=(
            BACKEND_DIR
            / "data"
            / "mock_policies"
            / "collateral"
            / "processed"
            / "collateral.json"
        ),
    ),
    "compliance": Dataset(
        key="compliance",
        department="COMPLIANCE",
        path=(
            BACKEND_DIR
            / "data"
            / "mock_policies"
            / "compliance"
            / "processed"
            / "compliance.json"
        ),
    ),
    "credit": Dataset(
        key="credit",
        department="CREDIT",
        path=(
            BACKEND_DIR
            / "data"
            / "mock_policies"
            / "credit"
            / "processed"
            / "credit.json"
        ),
    ),
    "customer_relationship": Dataset(
        key="customer_relationship",
        department="CUSTOMER_RELATIONSHIP",
        path=(
            BACKEND_DIR
            / "data"
            / "mock_policies"
            / "customer_relationship"
            / "processed"
            / "customer_relationship.json"
        ),
    ),
}


@dataclass(frozen=True)
class ChunkRecord:
    content: str
    metadata: dict[str, Any]


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _legacy_content(chunk: dict[str, Any]) -> str:
    content = chunk.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    return json.dumps(chunk, ensure_ascii=False, sort_keys=True)


def load_dataset(dataset: Dataset) -> list[ChunkRecord]:
    """Load either a wrapped department document or a legacy JSON list."""
    with dataset.path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    if isinstance(document, dict) and isinstance(document.get("chunks"), list):
        raw_chunks = document["chunks"]
        schema_version = document.get("schema_version")
        source_warnings = document.get("quality_report", {}).get("source_warnings", [])
    elif isinstance(document, list):
        raw_chunks = document
        schema_version = "legacy"
        source_warnings = []
    else:
        raise ValueError(f"Unsupported JSON structure in {dataset.path}")

    warnings_by_document: dict[str, list[dict[str, Any]]] = {}
    for warning in source_warnings:
        if not isinstance(warning, dict) or not warning.get("document_id"):
            continue
        warnings_by_document.setdefault(str(warning["document_id"]), []).append(warning)

    records: list[ChunkRecord] = []
    seen_hashes: set[str] = set()
    for index, chunk in enumerate(raw_chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk {index} in {dataset.path} is not an object")

        raw_content = chunk.get("content_chunk")
        content = (
            raw_content.strip()
            if isinstance(raw_content, str) and raw_content.strip()
            else _legacy_content(chunk)
        )
        digest = content_sha256(content)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)

        source_metadata = chunk.get("metadata")
        metadata = dict(source_metadata) if isinstance(source_metadata, dict) else {}
        payload = chunk.get("payload")
        if isinstance(payload, dict):
            metadata["payload"] = payload

        chunk_id = chunk.get("chunk_id") or metadata.get("chunk_id")
        metadata.update(
            {
                "department": dataset.department,
                "chunk_type": chunk.get("chunk_type", "POLICY_RULE"),
                "content_sha256": digest,
                "source_json": str(dataset.path.relative_to(BACKEND_DIR)),
                "schema_version": schema_version,
            }
        )
        if chunk_id:
            metadata["chunk_id"] = chunk_id

        document_warnings = warnings_by_document.get(str(metadata.get("document_id")), [])
        if document_warnings:
            metadata["source_warnings"] = document_warnings
            blocking_codes = sorted(
                {
                    str(warning.get("code"))
                    for warning in document_warnings
                    if warning.get("code") in BLOCKING_SOURCE_WARNING_CODES
                }
            )
            if blocking_codes:
                metadata["indexing_blocked"] = True
                metadata["indexing_blocked_codes"] = blocking_codes

        # Preserve useful legacy fields without embedding the metadata itself.
        if schema_version == "legacy":
            for key, value in chunk.items():
                if key not in {"content", "content_chunk", "metadata", "payload"}:
                    metadata.setdefault(key, value)

        records.append(ChunkRecord(content=content, metadata=metadata))

    return records


def deterministic_mock_embedding(text: str) -> list[float]:
    """Return a stable normalized vector for DB integration tests only."""
    values: list[float] = []
    counter = 0
    while len(values) < EMBEDDING_DIMENSIONS:
        digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
        values.extend((byte / 127.5) - 1.0 for byte in digest)
        counter += 1
    values = values[:EMBEDDING_DIMENSIONS]
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values]


def batches(items: Sequence[ChunkRecord], size: int) -> Iterable[Sequence[ChunkRecord]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def create_embedder(provider: str):
    if provider == "mock":
        return None

    from app.config import get_settings
    from app.services.embeddings import get_configured_embeddings

    settings = get_settings()
    if settings.embedding_dimensions != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"EMBEDDING_DIMENSIONS={settings.embedding_dimensions} is incompatible "
            f"with the database Vector({EMBEDDING_DIMENSIONS}) column."
        )
    if provider not in {"fpt", "glm", "local"} or settings.embedding_provider != provider:
        raise RuntimeError(
            f"Provider {provider!r} requires EMBEDDING_PROVIDER={provider} in .env."
        )
    return get_configured_embeddings()


def embed_batch(embedder, provider: str, records: Sequence[ChunkRecord]) -> list[list[float]]:
    if provider == "mock":
        vectors = [deterministic_mock_embedding(record.content) for record in records]
    else:
        vectors = embedder.embed_documents([record.content for record in records])

    for index, vector in enumerate(vectors):
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Embedding {index} has {len(vector)} dimensions; "
                f"database schema requires {EMBEDDING_DIMENSIONS}."
            )
    return vectors


def existing_content_hashes(db, department: str) -> set[str]:
    from sqlalchemy import select

    from app.db.models import PolicyEmbedding

    rows = db.execute(
        select(PolicyEmbedding.content_chunk, PolicyEmbedding.metadata_).where(
            PolicyEmbedding.metadata_["department"].astext == department
        )
    ).all()
    hashes: set[str] = set()
    for content, metadata in rows:
        if isinstance(metadata, dict) and metadata.get("content_sha256"):
            hashes.add(str(metadata["content_sha256"]))
        else:
            hashes.add(content_sha256(content))
    return hashes


def initialize_database() -> None:
    from sqlalchemy import text

    from app.db.models import Base
    from app.db.session import engine

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        table_exists = connection.execute(
            text("SELECT to_regclass('public.policy_embeddings') IS NOT NULL")
        ).scalar_one()
        if table_exists:
            current_dimensions = connection.execute(
                text(
                    """
                    SELECT atttypmod
                    FROM pg_attribute
                    WHERE attrelid = 'policy_embeddings'::regclass
                      AND attname = 'embedding'
                    """
                )
            ).scalar_one()
            if current_dimensions != EMBEDDING_DIMENSIONS:
                record_count = connection.execute(
                    text("SELECT count(*) FROM policy_embeddings")
                ).scalar_one()
                if record_count:
                    raise RuntimeError(
                        f"policy_embeddings contains {record_count} record(s) with "
                        f"Vector({current_dimensions}). Re-embed or migrate them before "
                        f"switching to Vector({EMBEDDING_DIMENSIONS})."
                    )
                connection.execute(
                    text(
                        "ALTER TABLE policy_embeddings "
                        f"ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSIONS})"
                    )
                )
                print(
                    f"Migrated empty policy_embeddings table from "
                    f"Vector({current_dimensions}) to Vector({EMBEDDING_DIMENSIONS})."
                )
    Base.metadata.create_all(bind=engine)


def embed_and_store_chunks(
    datasets: Sequence[Dataset],
    provider: str,
    batch_size: int,
    allow_external_source: bool = False,
) -> tuple[int, int, int]:
    from app.config import get_settings
    from app.db.models import PolicyEmbedding
    from app.db.session import SessionLocal

    initialize_database()
    embedder = create_embedder(provider)
    settings = get_settings()
    model_name = (
        settings.embedding_model
        if provider in {"fpt", "glm", "local"}
        else "deterministic-sha256-mock"
    )

    inserted = 0
    skipped = 0
    blocked = 0
    with SessionLocal() as db:
        try:
            for dataset in datasets:
                loaded_records = load_dataset(dataset)
                blocked_records = [
                    record
                    for record in loaded_records
                    if record.metadata.get("indexing_blocked")
                ]
                records = (
                    loaded_records
                    if allow_external_source
                    else [
                        record
                        for record in loaded_records
                        if not record.metadata.get("indexing_blocked")
                    ]
                )
                blocked_for_dataset = 0 if allow_external_source else len(blocked_records)
                blocked += blocked_for_dataset
                existing = existing_content_hashes(db, dataset.department)
                pending = [
                    record
                    for record in records
                    if record.metadata["content_sha256"] not in existing
                ]
                skipped += len(records) - len(pending)
                print(
                    f"{dataset.department}: {len(records)} valid, "
                    f"{len(pending)} pending, {len(records) - len(pending)} existing, "
                    f"{blocked_for_dataset} blocked by source quality gate"
                )

                for record_batch in batches(pending, batch_size):
                    vectors = embed_batch(embedder, provider, record_batch)
                    objects = []
                    for record, vector in zip(record_batch, vectors, strict=True):
                        metadata = dict(record.metadata)
                        metadata.update(
                            {
                                "embedding_provider": provider,
                                "embedding_model": model_name,
                                "embedding_dimensions": EMBEDDING_DIMENSIONS,
                            }
                        )
                        objects.append(
                            PolicyEmbedding(
                                content_chunk=record.content,
                                embedding=vector,
                                metadata_=metadata,
                            )
                        )
                    db.add_all(objects)
                    db.commit()
                    inserted += len(objects)
                    print(f"  inserted {inserted} record(s) in this run")
        except Exception:
            db.rollback()
            raise
    return inserted, skipped, blocked


def dry_run(datasets: Sequence[Dataset], allow_external_source: bool = False) -> int:
    total = 0
    total_blocked = 0
    for dataset in datasets:
        if not dataset.path.exists():
            print(f"{dataset.department}: missing {dataset.path}")
            continue
        loaded_records = load_dataset(dataset)
        blocked_records = [
            record for record in loaded_records if record.metadata.get("indexing_blocked")
        ]
        records = (
            loaded_records
            if allow_external_source
            else [
                record
                for record in loaded_records
                if not record.metadata.get("indexing_blocked")
            ]
        )
        blocked_count = 0 if allow_external_source else len(blocked_records)
        total += len(records)
        total_blocked += blocked_count
        chunk_types: dict[str, int] = {}
        for record in records:
            chunk_type = str(record.metadata["chunk_type"])
            chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
        print(
            f"{dataset.department}: {len(records)} eligible chunks, "
            f"{blocked_count} blocked; "
            f"types={json.dumps(chunk_types, ensure_ascii=False, sort_keys=True)}"
        )
    print(
        f"Dry run complete: {total} chunks ready, {total_blocked} blocked; "
        "no API or database calls made."
    )
    return total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--departments",
        nargs="+",
        choices=sorted(DATASETS),
        default=list(DATASETS),
        help="Datasets to process (default: all seven departments).",
    )
    provider_group = parser.add_mutually_exclusive_group()
    provider_group.add_argument(
        "--provider",
        choices=("fpt", "glm", "local", "mock"),
        default="fpt",
        help="Embedding provider. Mock is only for local DB integration tests.",
    )
    provider_group.add_argument(
        "--mock",
        action="store_const",
        const="mock",
        dest="provider",
        help="Alias for --provider mock; never use mock vectors in production.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Embedding/API batch size (default: {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and count input chunks without API or database access.",
    )
    parser.add_argument(
        "--allow-external-source",
        action="store_true",
        help=(
            "Allow chunks flagged EXTERNAL_INSTITUTION_REFERENCE. "
            "Use only after explicit domain-owner approval."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    selected = [DATASETS[key] for key in args.departments]
    missing = [str(dataset.path) for dataset in selected if not dataset.path.exists()]
    if missing:
        raise FileNotFoundError("Missing dataset(s): " + ", ".join(missing))

    if args.dry_run:
        dry_run(selected, allow_external_source=args.allow_external_source)
        return 0

    inserted, skipped, blocked = embed_and_store_chunks(
        selected,
        args.provider,
        args.batch_size,
        allow_external_source=args.allow_external_source,
    )
    print(
        f"Completed: inserted={inserted}, skipped_existing={skipped}, "
        f"blocked={blocked}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
