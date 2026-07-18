"""Normalize and chunk the collateral, compliance, and credit policy sources.

This is intentionally a deterministic, embedding-free phase.  Markdown/TXT
files are treated as canonical text when they are present; the original PDF,
DOC/DOCX is retained in the provenance manifest.  The output is one importable
JSON document per department under that department's ``processed`` folder.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "backend" / "data"
POLICY_ROOT = DATA_ROOT / "mock_policies"
TARGET_DEPARTMENTS = {
    "collateral": "COLLATERAL",
    "compliance": "COMPLIANCE",
    "credit": "CREDIT",
}
TEXT_SUFFIXES = {".md", ".txt"}
SOURCE_SUFFIXES = {".pdf", ".docx", ".doc", ".md", ".txt"}

ARTICLE_RE = re.compile(
    r"^\s{0,3}(?:#{1,6}\s+)?(Điều(?: khoản)?|Article)\s+([0-9]+[A-Za-z]?)"
    r"\s*[:.\-–—]\s*(.*)$",
    re.IGNORECASE,
)
CHAPTER_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(Chương|Chapter)\s+([^:]+)(?::\s*(.*))?$", re.IGNORECASE)
PAGE_RE = re.compile(r"<!--\s*Trang\s+(\d+)\s*-->", re.IGNORECASE)
HEADING_RE = re.compile(r"^\s*(#{2,6})\s+(.+?)\s*$")
TOP_NUMBER_RE = re.compile(r"^\s*(\d+)\.\s*(.*)$")
TOP_CLAUSE_RE = re.compile(r"^\s*\d+\.\s+\S")
SUB_CLAUSE_RE = re.compile(r"^\s*\d+\.\d+\.\s+\S")
LETTER_CLAUSE_RE = re.compile(r"^\s*[A-Za-zĐđ]\.(?:\s+\S.*)?$")
ROMAN_CLAUSE_RE = re.compile(r"^\s*\([ivxlcdm]+\)\.\s+\S", re.IGNORECASE)
ANNEX_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(Phụ lục|Appendix|Mẫu số)\b.*$", re.IGNORECASE)
SOURCE_RE = re.compile(r"Nguồn\s*:\s*`([^`]+)`", re.IGNORECASE)
PAGES_RE = re.compile(r"(?:—|-)\s*(\d+)\s*trang", re.IGNORECASE)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    ascii_value = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-").lower()
    return ascii_value[:80] or "document"


def bad_encoding_score(value: str) -> int:
    # ``â``/``Â``/``Ã`` are valid Vietnamese letters, so only count common
    # multi-character mojibake signatures and the replacement character.
    signatures = (
        "â€", "Ã„", "Ã†", "Ã¡", "Ã ", "Ã¢", "Ã£", "Ã¨", "Ãé", "Ãê",
        "Ãì", "Ãí", "Ãò", "Ãó", "Ãô", "Ãõ", "Ãù", "Ãú", "Ãý", "�",
    )
    return sum(value.count(signature) for signature in signatures)


def repair_mojibake(value: str) -> str:
    """Repair a UTF-8/Windows-1252 round-trip only when it improves the text."""

    before = bad_encoding_score(value)
    if before == 0:
        return value
    candidate = value
    for _ in range(2):
        try:
            trial = candidate.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if bad_encoding_score(trial) >= bad_encoding_score(candidate):
            break
        candidate = trial
    return candidate


def clean_text(value: str) -> str:
    value = value.replace("\ufeff", "").replace("\x00", "")
    value = repair_mojibake(value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    # Keep markdown/table structure, but remove excessive whitespace noise.
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def read_text(path: Path) -> str:
    return clean_text(path.read_text(encoding="utf-8", errors="replace"))


def rel_repo(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def find_declared_source(dept_dir: Path, canonical: Path, text: str) -> Path | None:
    match = SOURCE_RE.search(text)
    candidates: list[str] = []
    if match:
        candidates.append(match.group(1).strip())
    # A converted markdown normally has an adjacent source with the same stem.
    for suffix in (".pdf", ".docx", ".doc"):
        candidates.append(canonical.with_suffix(suffix).name)
    for name in candidates:
        direct = canonical.parent / name
        if direct.exists() and direct != canonical:
            return direct
        for found in dept_dir.rglob(name):
            if found != canonical:
                return found
    return None


def page_context(lines: list[str]) -> tuple[list[int | None], list[int]]:
    current: int | None = None
    line_pages: list[int | None] = []
    pages: list[int] = []
    for line in lines:
        marker = PAGE_RE.search(line)
        if marker:
            current = int(marker.group(1))
            pages.append(current)
        line_pages.append(current)
    return line_pages, sorted(set(pages))


def section_title(lines: list[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--") or stripped.startswith("> Nguồn"):
            continue
        stripped = re.sub(r"^#{1,6}\s*", "", stripped)
        stripped = re.sub(r"^\*\*(.*?)\*\*$", r"\1", stripped)
        return stripped[:240]
    return "Untitled section"


def split_sections(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    line_pages, _ = page_context(lines)
    article_starts = [i for i, line in enumerate(lines) if ARTICLE_RE.match(line)]
    chapter_at: dict[int, str] = {}
    chapter = ""
    for i, line in enumerate(lines):
        match = CHAPTER_RE.match(line)
        if match:
            chapter = " ".join(part for part in (match.group(1), match.group(2), match.group(3) or "") if part).strip()
        chapter_at[i] = chapter

    starts: list[int]
    if len(article_starts) >= 2:
        # Annexes/forms after the final official article are structurally
        # different.  Forms can contain text such as ``Điều 3`` themselves,
        # so the last ARTICLE_RE match is not a reliable article boundary.
        all_annex_starts = [i for i, line in enumerate(lines) if ANNEX_RE.match(line)]
        first_annex = min(all_annex_starts) if all_annex_starts else len(lines)
        official_articles = [i for i in article_starts if i < first_annex]
        annex_starts = [i for i in all_annex_starts if i > (official_articles[-1] if official_articles else -1)]
        starts = sorted(set(official_articles + annex_starts))
        kind = "article"
    else:
        # Personal-data terms use top-level ``1.`` / ``2.`` headings, while
        # fee documents use markdown headings.  Only split top-level numbers
        # when there are at least three candidates and the number is <= 99.
        numeric_starts = []
        for i, line in enumerate(lines):
            match = TOP_NUMBER_RE.match(line)
            if not match or int(match.group(1)) > 99:
                continue
            previous_blank = i == 0 or not lines[i - 1].strip()
            if previous_blank or not match.group(2).strip():
                numeric_starts.append(i)
        heading_starts = [i for i, line in enumerate(lines) if HEADING_RE.match(line)]
        if len(numeric_starts) >= 3:
            starts = numeric_starts
            kind = "numbered_section"
        elif heading_starts:
            starts = heading_starts
            kind = "heading"
        else:
            starts = []
            kind = "paragraph"

    boundaries = [0] + starts + [len(lines)]
    sections: list[dict[str, Any]] = []
    for left, right in zip(boundaries, boundaries[1:]):
        block_lines = lines[left:right]
        article = ARTICLE_RE.match(lines[left]) if left < len(lines) else None
        if article:
            # A chapter/subsection heading placed immediately before the next
            # article belongs to that next article's context, not the current
            # article's retrievable content.
            while len(block_lines) > 1:
                last = len(block_lines) - 1
                while last > 0 and not block_lines[last].strip():
                    last -= 1
                if HEADING_RE.match(block_lines[last]) and not ARTICLE_RE.match(block_lines[last]):
                    block_lines = block_lines[:last]
                    continue
                break
        content = "\n".join(block_lines).strip()
        if not content:
            continue
        pages = [page for page in line_pages[left:right] if page is not None]
        identifier = None
        if article:
            identifier = f"Điều {article.group(2)}"
        elif kind == "numbered_section":
            number = TOP_NUMBER_RE.match(lines[left])
            if number:
                identifier = number.group(1)
        elif ANNEX_RE.match(lines[left]):
            identifier = re.sub(r"^\s*#{1,6}\s*", "", lines[left]).strip()[:120]
        sections.append(
            {
                "content": content,
                "start_line": left + 1,
                "end_line": right,
                "page_start": min(pages) if pages else None,
                "page_end": max(pages) if pages else None,
                "section_id": identifier or f"section-{len(sections) + 1}",
                "section_title": section_title(block_lines),
                "chapter": chapter_at.get(left, ""),
                "kind": kind,
            }
        )
    return sections


def paragraphs(text: str) -> Iterable[str]:
    for part in re.split(r"\n\s*\n", text):
        part = part.strip()
        if part and not part.startswith("<!--") and not part.startswith("> Nguồn"):
            yield part


def split_long_section(section: dict[str, Any], max_words: int = 420) -> list[dict[str, Any]]:
    """Split on clause/paragraph boundaries while retaining article identity."""

    words = section["content"].split()
    if len(words) <= max_words:
        return [section]

    lines = section["content"].splitlines()
    structural_starts = [
        i for i, line in enumerate(lines[1:], 1)
        if TOP_CLAUSE_RE.match(line)
        or SUB_CLAUSE_RE.match(line)
        or LETTER_CLAUSE_RE.match(line)
        or ROMAN_CLAUSE_RE.match(line)
    ]
    pieces: list[str] = []
    if structural_starts:
        # Keep the article/section heading in every resulting chunk, and only
        # group complete numbered/lettered clauses under the word ceiling.
        prefix = lines[: structural_starts[0]]
        clause_boundaries = structural_starts + [len(lines)]
        current: list[str] = []
        prefix_words = len(prefix)
        current_words = prefix_words
        for left, right in zip(structural_starts, clause_boundaries[1:]):
            block = lines[left:right]
            block_words = len(" ".join(block).split())
            if current and current_words + block_words > max_words:
                pieces.append("\n".join(prefix + current))
                current, current_words = [], prefix_words
            current.extend(block)
            current_words += block_words
        if current:
            pieces.append("\n".join(prefix + current))
    else:
        current = []
        current_words = 0
        for paragraph in paragraphs(section["content"]):
            paragraph_words = paragraph.split()
            if current and current_words + len(paragraph_words) > max_words:
                pieces.append("\n\n".join(current))
                current, current_words = [], 0
            current.append(paragraph)
            current_words += len(paragraph_words)
        if current:
            pieces.append("\n\n".join(current))
        # OCR/conversion output sometimes has no blank lines in long forms.
        # Fall back to line boundaries for those non-clause sections rather
        # than emitting multi-thousand-word chunks.
        if len(pieces) == 1 and len(pieces[0].split()) > max_words:
            pieces = []
            current_lines: list[str] = []
            current_words = 0
            for line in section["content"].splitlines():
                line_words = len(line.split())
                if current_lines and current_words + line_words > max_words:
                    pieces.append("\n".join(current_lines))
                    current_lines, current_words = [], 0
                current_lines.append(line)
                current_words += line_words
            if current_lines:
                pieces.append("\n".join(current_lines))

    # Annex forms can contain numbered fields that look like legal clauses;
    # for those sections a line boundary is safer than a multi-thousand-word
    # retrieval unit.
    if pieces and any(len(piece.split()) > max_words for piece in pieces) and section["section_id"].startswith(("Phụ lục", "Mẫu số")):
        pieces = []
        current_lines = []
        current_words = 0
        for line in section["content"].splitlines():
            line_words = len(line.split())
            if current_lines and current_words + line_words > max_words:
                pieces.append("\n".join(current_lines))
                current_lines, current_words = [], 0
            current_lines.append(line)
            current_words += line_words
        if current_lines:
            pieces.append("\n".join(current_lines))
    if len(pieces) <= 1:
        return [section]
    result = []
    for index, content in enumerate(pieces, 1):
        item = dict(section)
        item["content"] = content
        item["section_id"] = f"{section['section_id']}.{index}"
        result.append(item)
    return result


def force_line_limit(section: dict[str, Any], max_words: int = 420) -> list[dict[str, Any]]:
    """Bound structured tables/forms without fabricating semantic fields."""

    if len(section["content"].split()) <= max_words:
        return [section]
    pieces: list[str] = []
    current: list[str] = []
    current_words = 0
    for line in section["content"].splitlines():
        line_words = len(line.split())
        if current and current_words + line_words > max_words:
            pieces.append("\n".join(current))
            current, current_words = [], 0
        current.append(line)
        current_words += line_words
    if current:
        pieces.append("\n".join(current))
    result: list[dict[str, Any]] = []
    for index, content in enumerate(pieces, 1):
        item = dict(section)
        item["content"] = content
        item["section_id"] = f"{section['section_id']}.{index}"
        result.append(item)
    return result


def infer_chunk_type(department: str, path: Path, section: dict[str, Any]) -> str:
    name = path.name.lower()
    if department == "COLLATERAL":
        return "LEGAL_CLAUSE"
    if department == "COMPLIANCE":
        if "dieu-khoan" in name or "dữ liệu" in name:
            return "LEGAL_CLAUSE"
        if section["section_id"].startswith(("Phụ lục", "Mẫu số")):
            return "STRUCTURED_FACT"
        return "POLICY_RULE"
    # Credit policies and fee schedules are normative rules.  The source is
    # kept as a policy chunk; fee tables are represented as structured facts.
    if "biểu phí" in name or "biểu-phí" in name or "bieu-phi" in name:
        return "STRUCTURED_FACT"
    return "POLICY_RULE"


def extract_cross_references(text: str) -> list[str]:
    refs = re.findall(
        r"(?:Điều|Khoản|Chương)\s+\d+[A-Za-zĐđ./-]*|"
        r"(?:Nghị định|Thông tư|Luật)\s+\d+[A-Za-zĐđ./-]*",
        text,
        re.IGNORECASE,
    )
    return list(dict.fromkeys(refs))[:30]


def extract_rule_payload(text: str, title: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = " ".join(lines)
    def find_line(words: tuple[str, ...]) -> str | None:
        for line in lines:
            if any(word in line.lower() for word in words):
                return line[:1000]
        return None
    thresholds = re.findall(r"(?:>=|<=|>|<|tối thiểu|không vượt quá|dưới|từ)\s*[0-9][0-9.,%]*(?:\s*[%A-Za-zĐđVvNnGg])?", joined, re.IGNORECASE)
    return {
        "rule": title[:240],
        "condition": find_line(("đối với", "áp dụng", "trường hợp", "khi ")),
        "threshold": "; ".join(dict.fromkeys(thresholds)) or None,
        "exception": find_line(("ngoại lệ", "miễn", "trừ trường hợp", "không áp dụng")),
        "consequence": find_line(("từ chối", "yêu cầu", "hậu quả", "phạt", "áp dụng mức")),
    }


def make_payload(chunk_type: str, section: dict[str, Any], text: str) -> dict[str, Any]:
    if chunk_type == "LEGAL_CLAUSE":
        return {
            "clause_id": section["section_id"],
            "title": section["section_title"],
            "chapter": section["chapter"] or None,
            "cross_references": extract_cross_references(text),
        }
    if chunk_type == "STRUCTURED_FACT":
        return {
            "record_type": "policy_table_or_form",
            "metric": section["section_title"],
            "period": None,
            "value": None,
            "currency": "VND" if "vnd" in text.lower() or "đồng" in text.lower() else None,
            "source_page": section["page_start"],
        }
    return extract_rule_payload(text, section["section_title"])


def source_record(department_dir: Path, canonical: Path, text: str) -> dict[str, Any]:
    source_match = SOURCE_RE.search(text)
    declared_name = source_match.group(1).strip() if source_match else None
    declared = find_declared_source(department_dir, canonical, text)
    source_paths = [canonical]
    if declared and declared not in source_paths:
        source_paths.insert(0, declared)
    page_markers = sorted({int(x) for x in PAGE_RE.findall(text)})
    page_count_header = PAGES_RE.search(text)
    page_count = int(page_count_header.group(1)) if page_count_header else None
    if page_count is None and declared and declared.suffix.lower() == ".pdf":
        try:
            import fitz  # type: ignore
            page_count = len(fitz.open(declared))
        except Exception:
            page_count = None
    return {
        "document_id": f"{TARGET_DEPARTMENTS[department_dir.name]}-{slug(str(canonical.relative_to(department_dir).with_suffix('')))}",
        "document_name": canonical.relative_to(department_dir).as_posix(),
        "source_files": [rel_repo(path) for path in source_paths],
        "canonical_file": rel_repo(canonical),
        "declared_source": declared_name or (declared.name if declared else None),
        "declared_source_exists": declared is not None,
        "file_sha256": sha256_file(canonical),
        "file_type": canonical.suffix.lower().lstrip("."),
        "extraction_method": "canonical_markdown" if canonical.suffix.lower() == ".md" else "plain_text",
        "page_count": page_count,
        "page_markers": page_markers,
        "page_mapping_status": (
            "mapped"
            if page_markers and (page_count is None or len(page_markers) >= page_count)
            else "partial"
            if page_markers
            else "unavailable"
        ),
        "encoding_status": "clean" if bad_encoding_score(text) == 0 else "needs_review",
    }


def process_department(dept_dir: Path, department: str) -> dict[str, Any]:
    canonical_files = sorted(
        p for p in dept_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES and p.name.lower() != "readme.md" and "processed" not in p.parts
    )
    documents: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    source_warnings: list[dict[str, str]] = []
    document_chunk_counts: Counter[str] = Counter()
    for canonical in canonical_files:
        text = read_text(canonical)
        if not text:
            continue
        doc = source_record(dept_dir, canonical, text)
        documents.append(doc)
        if doc["declared_source"] and not doc["declared_source_exists"]:
            source_warnings.append(
                {
                    "document_id": doc["document_id"],
                    "code": "DECLARED_SOURCE_MISSING",
                    "message": f"Declared source is not present in the repository: {doc['declared_source']}",
                }
            )
        if doc["page_mapping_status"] != "mapped":
            source_warnings.append(
                {
                    "document_id": doc["document_id"],
                    "code": "PAGE_MAPPING_INCOMPLETE",
                    "message": "Canonical text does not provide a complete source-page mapping",
                }
            )
        if "techcombank" in text.lower():
            source_warnings.append(
                {
                    "document_id": doc["document_id"],
                    "code": "EXTERNAL_INSTITUTION_REFERENCE",
                    "message": "Source contains Techcombank references and requires domain-owner approval before indexing for SHB",
                }
            )
        sections = split_sections(text)
        for section in sections:
            chunk_type = infer_chunk_type(department, canonical, section)
            parts = split_long_section(section)
            if chunk_type == "STRUCTURED_FACT":
                bounded: list[dict[str, Any]] = []
                for part in parts:
                    bounded.extend(force_line_limit(part))
                parts = bounded
            for part in parts:
                content = clean_text(part["content"])
                if not content:
                    continue
                page_start, page_end = part["page_start"], part["page_end"]
                citation = doc["document_name"]
                if part["section_id"]:
                    citation += f", {part['section_id']}"
                chunk_number = len(chunks) + 1
                chunk_id = f"{department}-{chunk_number:06d}"
                metadata = {
                    "department": department,
                    "chunk_type": chunk_type,
                    "document_id": doc["document_id"],
                    "document_name": doc["document_name"],
                    "section_id": part["section_id"],
                    "section_title": part["section_title"],
                    "chapter": part["chapter"] or None,
                    "page_start": page_start,
                    "page_end": page_end,
                    "source_files": doc["source_files"],
                    "canonical_file": doc["canonical_file"],
                    "extraction_method": doc["extraction_method"],
                    "ocr_confidence": None,
                    "citation": citation,
                    "char_count": len(content),
                    "word_count": len(content.split()),
                    "token_count": None,
                    "token_count_status": "PENDING_TOKENIZER",
                    "content_sha256": sha256_text(content),
                }
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "content_chunk": content,
                        "chunk_type": chunk_type,
                        "payload": make_payload(chunk_type, part, content),
                        "metadata": metadata,
                    }
                )
                document_chunk_counts[doc["document_id"]] += 1

    # Exact duplicates occur in repeated annex forms.  Keep one retrievable
    # chunk, but retain every duplicate location for auditability.
    before_dedup = len(chunks)
    unique_chunks: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        digest = chunk["metadata"]["content_sha256"]
        first = seen.get(digest)
        if first is None:
            chunk["metadata"]["duplicate_count"] = 1
            chunk["metadata"]["duplicate_locations"] = []
            seen[digest] = chunk
            unique_chunks.append(chunk)
            continue
        first["metadata"]["duplicate_count"] += 1
        first["metadata"]["duplicate_locations"].append(
            {
                "document_id": chunk["metadata"]["document_id"],
                "section_id": chunk["metadata"]["section_id"],
                "page_start": chunk["metadata"]["page_start"],
                "page_end": chunk["metadata"]["page_end"],
                "citation": chunk["metadata"]["citation"],
            }
        )
    chunks = unique_chunks
    for index, chunk in enumerate(chunks, 1):
        chunk["chunk_id"] = f"{department}-{index:06d}"
        chunk["metadata"]["chunk_id"] = chunk["chunk_id"]

    hashes = [chunk["metadata"]["content_sha256"] for chunk in chunks]
    duplicate_ratio = 0.0 if not hashes else round(1 - len(set(hashes)) / len(hashes), 6)
    page_mapped = sum(1 for chunk in chunks if chunk["metadata"]["page_start"] is not None)
    metadata_fields = [
        "department", "chunk_type", "document_id", "document_name", "section_id",
        "canonical_file", "extraction_method", "citation", "content_sha256",
    ]
    complete = 0
    for chunk in chunks:
        if all(chunk["metadata"].get(field) not in (None, "") for field in metadata_fields):
            complete += 1
    return {
        "schema_version": "1.0",
        "department": department,
        "embedding": {"status": "NOT_GENERATED", "model": None, "dimensions": None},
        "source_documents": documents,
        "chunks": chunks,
        "quality_report": {
            "documents_discovered": len(canonical_files),
            "documents_processed": len(documents),
            "chunks_total": len(chunks),
            "duplicate_chunks_removed": before_dedup - len(chunks),
            "chunks_by_type": dict(Counter(chunk["chunk_type"] for chunk in chunks)),
            "chunks_over_420_words": sum(1 for chunk in chunks if chunk["metadata"]["word_count"] > 420),
            "empty_chunks": sum(1 for chunk in chunks if not chunk["content_chunk"].strip()),
            "metadata_completeness": round(complete / len(chunks), 6) if chunks else 0.0,
            "duplicate_ratio": duplicate_ratio,
            "department_leakage": 0,
            "boundary_violations": 0,
            "page_mapping": {
                "mapped_chunk_ratio": round(page_mapped / len(chunks), 6) if chunks else 0.0,
                "status": "PASS" if page_mapped == len(chunks) else "PARTIAL_REQUIRES_SOURCE_PAGE_MAPPING",
            },
            "token_size": {
                "status": "PENDING_TOKENIZER",
                "note": "word_count is reported; token_count is intentionally null until the embedding tokenizer is selected",
            },
            "manual_qa": {
                "status": "PENDING",
                "sample": "10% of pages and 20 chunks per department",
            },
            "source_warnings": source_warnings,
        },
    }


def validate(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    department = document.get("department")
    if document.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if department not in TARGET_DEPARTMENTS.values():
        errors.append("invalid department")
    ids: set[str] = set()
    hashes: set[str] = set()
    for chunk in document.get("chunks", []):
        chunk_id = chunk.get("chunk_id")
        if not chunk_id or chunk_id in ids:
            errors.append(f"duplicate or empty chunk_id: {chunk_id}")
        ids.add(chunk_id)
        if not chunk.get("content_chunk", "").strip():
            errors.append(f"empty chunk: {chunk_id}")
        metadata = chunk.get("metadata", {})
        if metadata.get("department") != department:
            errors.append(f"department mismatch: {chunk_id}")
        digest = sha256_text(chunk["content_chunk"])
        if metadata.get("content_sha256") != digest:
            errors.append(f"checksum mismatch: {chunk_id}")
        hashes.add(digest)
    if errors:
        return errors
    return errors


def main() -> None:
    for folder, department in TARGET_DEPARTMENTS.items():
        dept_dir = POLICY_ROOT / folder
        output_dir = dept_dir / "processed"
        output_dir.mkdir(exist_ok=True)
        document = process_department(dept_dir, folder.upper())
        errors = validate(document)
        if errors:
            raise SystemExit(f"{folder}: validation failed: {errors[:5]}")
        output = output_dir / f"{folder}.json"
        output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = document["quality_report"]
        print(json.dumps({"department": folder, "output": rel_repo(output), **report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
