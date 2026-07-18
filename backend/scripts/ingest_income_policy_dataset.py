"""Chunk the current income-verification dataset and optionally embed it.

Only approved policy/procedure sources may enter the global policy index. The
``Income_analysis_agent`` folder is case evidence and is therefore reported,
but never embedded into ``policy_embeddings``. Demo-only synthetic policy can
be included explicitly for local evaluation; it remains marked
``DEMO_ONLY`` and is never indexed by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
DATASET_ROOT = REPO_ROOT / "dataset"
DEFAULT_OUTPUT = BACKEND_DIR / "data" / "rag" / "income_policy_corpus.json"
EMBEDDING_DIMENSIONS = 512
ALLOWED_CHUNK_TYPES = {"POLICY_RULE", "VERIFICATION_PROCEDURE"}
APPROVED_STATUS = "APPROVED"


@dataclass(frozen=True, slots=True)
class SourceDocument:
    path: Path
    metadata: dict[str, Any]
    body: str
    source_checksum: str
    page_count: int | None = None


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] == '"':
        return stripped[1:-1]
    if stripped.lower() == "null":
        return None
    if stripped.lower() in {"true", "false"}:
        return stripped.lower() == "true"
    return stripped


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.replace("\r\n", "\n").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text.strip()
    end = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if end is None:
        return {}, text.strip()
    metadata: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = parse_scalar(value)
    return metadata, "\n".join(lines[end + 1 :]).strip()


def read_pdf(path: Path) -> tuple[str, int]:
    import fitz

    pages: list[str] = []
    with fitz.open(path) as document:
        for page_number, page in enumerate(document, 1):
            pages.append(f"<!-- Trang {page_number} -->\n{page.get_text('text').strip()}")
        return "\n\n".join(pages).strip(), document.page_count


def read_source(path: Path) -> SourceDocument:
    raw = path.read_bytes()
    checksum = sha256_bytes(raw)
    page_count: int | None = None
    if path.suffix.lower() == ".pdf":
        body, page_count = read_pdf(path)
        metadata: dict[str, Any] = {}
    else:
        metadata, body = parse_front_matter(raw.decode("utf-8", errors="replace"))
    return SourceDocument(path, metadata, body, checksum, page_count)


def page_for_line(lines: list[str], line_index: int) -> int:
    page = 1
    for line in lines[: line_index + 1]:
        match = re.search(r"<!--\s*Trang\s+(\d+)\s*-->", line, re.IGNORECASE)
        if match:
            page = int(match.group(1))
    return page


def split_policy_sections(body: str) -> list[dict[str, Any]]:
    """Split only on markdown section headings, retaining each rule intact."""

    lines = body.splitlines()
    starts = [index for index, line in enumerate(lines) if re.match(r"^##\s+", line)]
    sections: list[dict[str, Any]] = []
    boundaries = starts + [len(lines)]
    for start, end in zip(starts, boundaries[1:]):
        content = "\n".join(lines[start:end]).strip()
        if not content:
            continue
        title = re.sub(r"^##\s+", "", lines[start]).strip()
        section_type = re.search(r"Chunk type:\s*\**\s*`([^`]+)`", content, re.IGNORECASE)
        section_id = re.search(r"Section ID:\s*\**\s*`([^`]+)`", content, re.IGNORECASE)
        if not section_type or not section_id:
            continue
        sections.append(
            {
                "title": title,
                "content": content,
                "chunk_type": section_type.group(1).strip().upper(),
                "section_id": section_id.group(1).strip(),
                "page_number": page_for_line(lines, start),
            }
        )
    return sections


def quarantine_entry(source: SourceDocument, code: str, reason: str) -> dict[str, Any]:
    return {
        "source_path": source.path.relative_to(REPO_ROOT).as_posix(),
        "source_checksum": source.source_checksum,
        "code": code,
        "reason": reason,
        "page_count": source.page_count,
    }


def build_corpus(*, include_demo: bool = False) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    source_count = 0
    policy_dir = DATASET_ROOT / "Policy_agent"
    income_dir = DATASET_ROOT / "Income_analysis_agent"

    for path in sorted(policy_dir.iterdir() if policy_dir.exists() else []):
        if not path.is_file():
            continue
        source_count += 1
        source = read_source(path)
        metadata = source.metadata
        if path.suffix.lower() != ".md" or not metadata:
            quarantine.append(
                quarantine_entry(
                    source,
                    "MISSING_APPROVED_METADATA",
                    "Policy PDFs/notes need an owner-approved manifest with effective dates, section and approval status before indexing.",
                )
            )
            continue
        if metadata.get("dataset_type") not in ALLOWED_CHUNK_TYPES:
            quarantine.append(
                quarantine_entry(source, "UNSUPPORTED_DATASET_TYPE", "Source is not a policy rule or verification procedure.")
            )
            continue
        status = str(metadata.get("approval_status") or "")
        demo_only = status == "APPROVED_FOR_DEMO" and metadata.get("production_use") == "prohibited"
        if status != APPROVED_STATUS and not (include_demo and demo_only):
            quarantine.append(
                quarantine_entry(source, "APPROVAL_STATUS_NOT_APPROVED", f"approval_status={status or 'MISSING'} is not production-approved.")
            )
            continue
        if not metadata.get("domain") or not metadata.get("product") or not metadata.get("effective_date"):
            quarantine.append(quarantine_entry(source, "REQUIRED_METADATA_MISSING", "domain, product and effective_date are required."))
            continue
        for section in split_policy_sections(source.body):
            if section["chunk_type"] not in ALLOWED_CHUNK_TYPES:
                quarantine.append(quarantine_entry(source, "CHUNK_TYPE_NOT_ALLOWED", section["chunk_type"]))
                continue
            chunk_id = f"{metadata['dataset_id']}-{section['section_id']}"
            content = section["content"]
            chunk_metadata = {
                "chunk_id": chunk_id,
                "chunk_type": section["chunk_type"],
                "domain": str(metadata["domain"]),
                "product": str(metadata["product"]),
                "document_name": str(metadata.get("document_name") or path.stem),
                "document_version": str(metadata.get("version") or "unknown"),
                "page_number": section["page_number"],
                "section_id": section["section_id"],
                "effective_date": str(metadata["effective_date"]),
                "expiry_date": metadata.get("effective_to"),
                "approval_status": "APPROVED_FOR_DEMO" if demo_only else APPROVED_STATUS,
                "source_path": path.relative_to(REPO_ROOT).as_posix(),
                "source_checksum": source.source_checksum,
                "content_sha256": sha256_text(content),
                "language": metadata.get("language", "vi"),
                "synthetic": bool(metadata.get("synthetic", False)),
                "indexing_scope": "DEMO_ONLY" if demo_only else "GLOBAL_POLICY",
            }
            chunks.append({
                "chunk_id": chunk_id,
                "content_chunk": content,
                "chunk_type": section["chunk_type"],
                "metadata": chunk_metadata,
            })

    for path in sorted(income_dir.iterdir() if income_dir.exists() else []):
        if path.is_file():
            source_count += 1
            quarantine.append(
                quarantine_entry(
                    read_source(path),
                    "CASE_EVIDENCE_NOT_GLOBAL_POLICY",
                    "Income analysis data is case-scoped evidence and must not enter the global policy embedding index.",
                )
            )

    return {
        "schema_version": "income-policy-rag-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
        "allowed_chunk_types": sorted(ALLOWED_CHUNK_TYPES),
        "chunks": chunks,
        "quarantine": quarantine,
        "quality_report": {
            "source_count": source_count,
            "chunk_count": len(chunks),
            "quarantine_count": len(quarantine),
            "demo_only_chunk_count": sum(1 for chunk in chunks if chunk["metadata"]["indexing_scope"] == "DEMO_ONLY"),
        },
    }


def deterministic_embedding(text: str) -> list[float]:
    values: list[float] = []
    counter = 0
    while len(values) < EMBEDDING_DIMENSIONS:
        digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
        values.extend((byte / 127.5) - 1.0 for byte in digest)
        counter += 1
    values = values[:EMBEDDING_DIMENSIONS]
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values]


def embed_corpus(corpus: dict[str, Any], provider: str) -> None:
    chunks = corpus["chunks"]
    if provider == "mock":
        vectors = [deterministic_embedding(chunk["content_chunk"]) for chunk in chunks]
        model = "deterministic-sha256-mock"
    else:
        sys.path.insert(0, str(BACKEND_DIR))
        from app.config import get_settings
        from app.services.embeddings import get_configured_embeddings

        settings = get_settings()
        if settings.embedding_dimensions != EMBEDDING_DIMENSIONS:
            raise RuntimeError("EMBEDDING_DIMENSIONS must be 512 in .env before real embedding.")
        embedder = get_configured_embeddings()
        vectors = embedder.embed_documents([chunk["content_chunk"] for chunk in chunks])
        model = settings.embedding_model
    for chunk, vector in zip(chunks, vectors, strict=True):
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}.")
        chunk["embedding"] = vector
        chunk["metadata"].update({
            "embedding_provider": provider,
            "embedding_model": model,
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
        })


def index_approved_corpus(corpus: dict[str, Any]) -> int:
    """Persist only production-approved chunks; demo/mock chunks are rejected."""

    chunks = corpus["chunks"]
    if not chunks:
        return 0
    if any(chunk["metadata"].get("indexing_scope") != "GLOBAL_POLICY" for chunk in chunks):
        raise ValueError("Demo-only chunks cannot be written to the global policy index.")
    if any("embedding" not in chunk for chunk in chunks):
        raise ValueError("Run with --embed before --index-db.")
    sys.path.insert(0, str(BACKEND_DIR))
    from app.db.session import SessionLocal
    from app.services.rag import index_policy_chunks

    provider = str(chunks[0]["metadata"].get("embedding_provider", ""))
    model = str(chunks[0]["metadata"].get("embedding_model", ""))
    vectors = [chunk["embedding"] for chunk in chunks]
    with SessionLocal() as db:
        return index_policy_chunks(
            db,
            chunks,
            vectors,
            embedding_provider=provider,
            embedding_model=model,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--include-demo", action="store_true", help="Include demo-only synthetic policy chunks.")
    parser.add_argument("--embed", action="store_true", help="Generate vectors into the output JSON.")
    parser.add_argument("--index-db", action="store_true", help="Write approved vectors to PostgreSQL/pgvector.")
    parser.add_argument("--provider", choices=("mock", "fpt", "glm", "local"), default="mock")
    args = parser.parse_args()
    corpus = build_corpus(include_demo=args.include_demo)
    if args.embed:
        embed_corpus(corpus, args.provider)
    if args.index_db:
        if args.provider == "mock":
            raise ValueError("Mock embeddings cannot be written to the global policy index.")
        indexed = index_approved_corpus(corpus)
        print(json.dumps({"indexed": indexed}, ensure_ascii=False))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(corpus["quality_report"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
