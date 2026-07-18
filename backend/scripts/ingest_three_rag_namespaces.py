"""Build three logical RAG corpora from the current Markdown dataset.

The three namespaces share one embedding batch/model but remain isolated in
metadata and output. Customer/case Markdown is quarantined; only reference
material is embedded into the review/demo corpus. This script does not write
the production policy index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
DATASET_ROOT = REPO_ROOT / "dataset"
DEFAULT_OUTPUT = BACKEND_DIR / "data" / "rag" / "three_rag_corpus.json"
DIMENSIONS = 512

NAMESPACE_CONFIG = {
    "DOCUMENT_EXTRACTION": DATASET_ROOT / "document_extraction_agent",
    "INCOME_ANALYSIS": DATASET_ROOT / "Income_analysis_agent",
    "POLICY": DATASET_ROOT / "Policy_agent",
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if value.lower() == "null":
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    lines = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "\n".join(lines).strip()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, "\n".join(lines).strip()
    metadata: dict[str, Any] = {}
    for line in lines[1:end]:
        if ":" not in line or not line.strip():
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = parse_scalar(value)
    return metadata, "\n".join(lines[end + 1 :]).strip()


def split_headings(body: str, *, minimum_level: int = 2) -> list[dict[str, Any]]:
    lines = body.splitlines()
    page = 1
    line_pages: list[int] = []
    for line in lines:
        marker = re.search(r"<!--\s*Trang\s+(\d+)\s*-->", line, re.IGNORECASE)
        if marker:
            page = int(marker.group(1))
        line_pages.append(page)
    heading_re = re.compile(rf"^{'#' * minimum_level}(?!#)\s+(.+)$")
    starts = [i for i, line in enumerate(lines) if heading_re.match(line)]
    sections: list[dict[str, Any]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        content = "\n".join(lines[start:end]).strip()
        if content:
            sections.append({"title": heading_re.match(lines[start]).group(1).strip(), "content": content, "page_number": line_pages[start]})
    return sections or ([{"title": "document", "content": body, "page_number": 1}] if body else [])


def section_chunk_type(namespace: str, metadata: dict[str, Any], title: str) -> str:
    if namespace == "POLICY" and metadata.get("dataset_type") == "POLICY_RULE":
        return "POLICY_RULE"
    return "VERIFICATION_PROCEDURE"


def is_case_source(namespace: str, metadata: dict[str, Any], path: Path) -> bool:
    if namespace == "INCOME_ANALYSIS" and (
        metadata.get("case_id") or metadata.get("dataset_type") == "STRUCTURED_FACT"
    ):
        return True
    if metadata.get("case_id") or "synthetic_income_verification_documents" in path.name:
        return True
    return False


def build_corpus() -> dict[str, Any]:
    namespaces: dict[str, dict[str, Any]] = {}
    for namespace, root in NAMESPACE_CONFIG.items():
        chunks: list[dict[str, Any]] = []
        quarantine: list[dict[str, Any]] = []
        for path in sorted(root.glob("*.md")) if root.exists() else []:
            metadata, body = read_markdown(path)
            source_path = path.relative_to(REPO_ROOT).as_posix()
            source_checksum = sha256_text(path.read_text(encoding="utf-8", errors="replace"))
            if is_case_source(namespace, metadata, path):
                quarantine.append({"source_path": source_path, "code": "CASE_EVIDENCE_NOT_GLOBAL", "reason": "Case evidence is not embedded in a shared RAG corpus."})
                continue
            sections = split_headings(body)
            for section_index, section in enumerate(sections, 1):
                chunk_type = section_chunk_type(namespace, metadata, section["title"])
                explicit_section = re.search(
                    r"Section ID:\s*\**\s*`([^`]+)`",
                    section["content"],
                    re.IGNORECASE,
                )
                section_id = (
                    explicit_section.group(1).strip()
                    if explicit_section
                    else metadata.get("dataset_id", path.stem) + f"-S{section_index:03d}"
                )
                scope = "GLOBAL_POLICY" if namespace == "POLICY" and metadata.get("approval_status") == "APPROVED" else "REVIEW_ONLY"
                chunk_metadata = {
                    "chunk_id": f"{namespace}-{section_id}",
                    "rag_namespace": namespace,
                    "chunk_type": chunk_type,
                    "domain": metadata.get("domain", "INCOME_VERIFICATION"),
                    "product": metadata.get("product", "UNSECURED_PERSONAL_LOAN"),
                    "document_name": metadata.get("document_name", path.stem),
                    "document_version": metadata.get("document_version", metadata.get("version", "unknown")),
                    "section_id": section_id,
                    "page_number": section["page_number"],
                    "effective_date": metadata.get("effective_date"),
                    "approval_status": metadata.get("approval_status", "PENDING_REVIEW"),
                    "source_path": source_path,
                    "source_checksum": source_checksum,
                    "content_sha256": sha256_text(section["content"]),
                    "indexing_scope": scope,
                    "language": metadata.get("language", "vi"),
                }
                chunks.append({
                    "chunk_id": chunk_metadata["chunk_id"],
                    "content_chunk": section["content"],
                    "chunk_type": chunk_type,
                    "metadata": chunk_metadata,
                })
        namespaces[namespace] = {
            "chunks": chunks,
            "quarantine": quarantine,
            "quality_report": {
                "chunk_count": len(chunks),
                "quarantine_count": len(quarantine),
                "review_only_count": sum(1 for chunk in chunks if chunk["metadata"]["indexing_scope"] == "REVIEW_ONLY"),
            },
        }
    return {
        "schema_version": "three-rag-namespaces-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "embedding_dimensions": DIMENSIONS,
        "namespaces": namespaces,
    }


def deterministic_embedding(text: str) -> list[float]:
    values: list[float] = []
    counter = 0
    while len(values) < DIMENSIONS:
        digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
        values.extend((byte / 127.5) - 1.0 for byte in digest)
        counter += 1
    values = values[:DIMENSIONS]
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values]


def embed_corpus(corpus: dict[str, Any], provider: str) -> None:
    all_chunks = [chunk for item in corpus["namespaces"].values() for chunk in item["chunks"]]
    if provider == "mock":
        vectors = [deterministic_embedding(chunk["content_chunk"]) for chunk in all_chunks]
        model = "deterministic-sha256-mock"
    else:
        sys.path.insert(0, str(BACKEND_DIR))
        from app.config import get_settings
        from app.services.embeddings import get_configured_embeddings

        settings = get_settings()
        if settings.embedding_dimensions != DIMENSIONS:
            raise RuntimeError("EMBEDDING_DIMENSIONS must be 512.")
        vectors = get_configured_embeddings().embed_documents([chunk["content_chunk"] for chunk in all_chunks])
        model = settings.embedding_model
    for chunk, vector in zip(all_chunks, vectors, strict=True):
        if len(vector) != DIMENSIONS:
            raise ValueError(f"Embedding dimension mismatch: expected {DIMENSIONS}.")
        chunk["embedding"] = vector
        chunk["metadata"].update({"embedding_provider": provider, "embedding_model": model, "embedding_dimensions": DIMENSIONS})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--embed", action="store_true")
    parser.add_argument("--provider", choices=("mock", "fpt", "glm", "local"), default="mock")
    args = parser.parse_args()
    corpus = build_corpus()
    if args.embed:
        embed_corpus(corpus, args.provider)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({namespace: item["quality_report"] for namespace, item in corpus["namespaces"].items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
