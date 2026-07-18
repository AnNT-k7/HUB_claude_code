from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass

from pypdf import PdfReader


class DocumentValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedDocument:
    sha256: str
    extracted_text: str
    structured_payload: dict[str, object] | None
    page_count: int | None


def _parse_json(payload: bytes) -> tuple[str, dict[str, object]]:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentValidationError("invalid UTF-8 JSON document") from exc
    if not isinstance(decoded, dict):
        raise DocumentValidationError("case JSON document must contain an object")
    normalized = {str(key): value for key, value in decoded.items()}
    return json.dumps(normalized, ensure_ascii=False, indent=2), normalized


def _parse_pdf(payload: bytes) -> tuple[str, int]:
    if not payload.startswith(b"%PDF-"):
        raise DocumentValidationError("file content is not a PDF")
    try:
        reader = PdfReader(io.BytesIO(payload), strict=True)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise DocumentValidationError("PDF could not be parsed safely") from exc
    page_text = "\n\n".join(
        f"--- PAGE {index} ---\n{text}"
        for index, text in enumerate(pages, start=1)
        if text
    )
    return page_text, len(reader.pages)


def parse_document(payload: bytes, content_type: str) -> ParsedDocument:
    if not payload:
        raise DocumentValidationError("document is empty")

    sha256 = hashlib.sha256(payload).hexdigest()
    normalized_type = content_type.split(";", 1)[0].strip().lower()

    if normalized_type == "application/json":
        text, structured = _parse_json(payload)
        return ParsedDocument(sha256, text, structured, None)

    if normalized_type == "application/pdf":
        text, page_count = _parse_pdf(payload)
        return ParsedDocument(sha256, text, None, page_count)

    if normalized_type == "text/plain":
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentValidationError("text document must be UTF-8") from exc
        return ParsedDocument(sha256, text, None, None)

    raise DocumentValidationError(f"unsupported content type: {normalized_type}")
