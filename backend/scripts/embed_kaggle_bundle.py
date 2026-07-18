"""Embed all department chunks on a Kaggle GPU and export JSON artifacts.

This script deliberately has no database or API dependency. It is intended to
run in a Kaggle notebook/terminal with a GPU and Internet enabled. The same
model and dimensions must be used by the runtime query embedder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "Alibaba-NLP/gte-Qwen2-1.5B-instruct"
EMBEDDING_DIMENSIONS = 1536
DEFAULT_BATCH_SIZE = 8
BLOCKING_WARNING_CODES = {"EXTERNAL_INSTITUTION_REFERENCE"}

DATASETS = {
    "legal": ("LEGAL", Path("backend/data/processed_chunks/legal_chunks.json")),
    "operations": (
        "OPERATIONS",
        Path("backend/data/processed_chunks/operations_chunks.json"),
    ),
    "risk": ("RISK", Path("backend/data/processed_chunks/risk_chunks.json")),
    "collateral": (
        "COLLATERAL",
        Path("backend/data/mock_policies/collateral/processed/collateral.json"),
    ),
    "compliance": (
        "COMPLIANCE",
        Path("backend/data/mock_policies/compliance/processed/compliance.json"),
    ),
    "credit": (
        "CREDIT",
        Path("backend/data/mock_policies/credit/processed/credit.json"),
    ),
    "customer_relationship": (
        "CUSTOMER_RELATIONSHIP",
        Path(
            "backend/data/mock_policies/customer_relationship/processed/"
            "customer_relationship.json"
        ),
    ),
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_chunks(path: Path, department: str) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(document, dict) and isinstance(document.get("chunks"), list):
        raw_chunks = document["chunks"]
        schema_version = document.get("schema_version", "unknown")
        source_warnings = document.get("quality_report", {}).get("source_warnings", [])
    elif isinstance(document, list):
        raw_chunks = document
        schema_version = "legacy"
        source_warnings = []
    else:
        raise ValueError(f"Unsupported chunk JSON structure: {path}")

    warnings_by_document: dict[str, list[dict[str, Any]]] = {}
    for warning in source_warnings:
        if isinstance(warning, dict) and warning.get("document_id"):
            warnings_by_document.setdefault(str(warning["document_id"]), []).append(warning)

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, chunk in enumerate(raw_chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk {index} in {path} is not an object")
        raw_content = chunk.get("content_chunk", chunk.get("content"))
        content = (
            raw_content.strip()
            if isinstance(raw_content, str) and raw_content.strip()
            else json.dumps(chunk, ensure_ascii=False, sort_keys=True)
        )
        digest = sha256_text(content)
        if digest in seen:
            continue
        seen.add(digest)
        metadata = dict(chunk.get("metadata", {}))
        metadata.setdefault("department", department)
        metadata.setdefault("chunk_type", chunk.get("chunk_type", "POLICY_RULE"))
        metadata["content_sha256"] = digest
        metadata["source_json"] = path.as_posix()
        metadata["schema_version"] = schema_version
        document_id = metadata.get("document_id")
        warnings = warnings_by_document.get(str(document_id), [])
        if warnings:
            metadata["source_warnings"] = warnings
            codes = sorted(
                str(item.get("code"))
                for item in warnings
                if item.get("code") in BLOCKING_WARNING_CODES
            )
            if codes:
                metadata["indexing_blocked"] = True
                metadata["indexing_blocked_codes"] = codes
        for key, value in chunk.items():
            if key not in {"content", "content_chunk", "metadata"}:
                metadata.setdefault(key, value)
        records.append(
            {
                "chunk_id": chunk.get("chunk_id") or f"{department.lower()}-{index + 1:06d}",
                "content_chunk": content,
                "chunk_type": metadata["chunk_type"],
                "payload": chunk.get("payload"),
                "metadata": metadata,
            }
        )
    return records


def embed_department(
    model: Any,
    records: list[dict[str, Any]],
    batch_size: int,
    allow_external_source: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [
        record
        for record in records
        if allow_external_source or not record["metadata"].get("indexing_blocked")
    ]
    blocked = [record for record in records if record not in eligible]
    outputs: list[dict[str, Any]] = []
    for start in range(0, len(eligible), batch_size):
        batch = eligible[start : start + batch_size]
        vectors = model.encode(
            [record["content_chunk"] for record in batch],
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        for record, vector in zip(batch, vectors, strict=True):
            values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
            if len(values) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"{record['chunk_id']} returned {len(values)} dimensions; "
                    f"expected {EMBEDDING_DIMENSIONS}"
                )
            output = dict(record)
            output["embedding"] = values
            output["metadata"] = dict(record["metadata"])
            output["metadata"].update(
                {
                    "embedding_provider": "sentence-transformers",
                    "embedding_model": model._model_name_or_path
                    if hasattr(model, "_model_name_or_path")
                    else DEFAULT_MODEL,
                    "embedding_dimensions": EMBEDDING_DIMENSIONS,
                }
            )
            outputs.append(output)
    return outputs, blocked


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--allow-external-source", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        args.model,
        device=args.device,
        trust_remote_code=True,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": "embedding-1.0",
        "model": args.model,
        "dimensions": EMBEDDING_DIMENSIONS,
        "normalized": True,
        "departments": {},
    }
    for key, (department, relative_path) in DATASETS.items():
        source = args.repo_root / relative_path
        records = load_chunks(source, department)
        outputs, blocked = embed_department(
            model, records, args.batch_size, args.allow_external_source
        )
        output_path = args.output_dir / f"{key}_embeddings.json"
        output_path.write_text(
            json.dumps(
                {
                    "schema_version": "embedding-1.0",
                    "department": department,
                    "embedding": {
                        "model": args.model,
                        "dimensions": EMBEDDING_DIMENSIONS,
                        "normalized": True,
                    },
                    "chunks": outputs,
                    "blocked_chunks": blocked,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        manifest["departments"][key] = {
            "source": relative_path.as_posix(),
            "input_chunks": len(records),
            "embedded_chunks": len(outputs),
            "blocked_chunks": len(blocked),
            "output": output_path.name,
        }
        print(
            f"{department}: input={len(records)} embedded={len(outputs)} "
            f"blocked={len(blocked)}"
        )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
