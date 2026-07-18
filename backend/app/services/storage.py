"""Case-scoped document storage boundary for the MVP."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone


SUPPORTED_DOCUMENT_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".md", ".txt"}


class DocumentStorageError(ValueError):
    """Raised for invalid file metadata or cross-case access."""


@dataclass(frozen=True, slots=True)
class StoredDocument:
    case_id: str
    application_id: str
    document_id: str
    file_name: str
    content_type: str
    checksum: str
    size_bytes: int
    created_at: datetime


class CaseScopedDocumentStore:
    """In-memory adapter with the same isolation contract as an object store.

    The MVP keeps bytes in process for deterministic tests. Production wiring can
    replace this class with MinIO without changing Document Agent contracts.
    """

    def __init__(self, *, max_size_bytes: int = 25 * 1024 * 1024) -> None:
        self.max_size_bytes = max_size_bytes
        self._metadata: dict[tuple[str, str], StoredDocument] = {}
        self._content: dict[tuple[str, str], bytes] = {}

    def put(
        self,
        *,
        case_id: str,
        application_id: str,
        document_id: str,
        file_name: str,
        content_type: str,
        content: bytes,
    ) -> StoredDocument:
        suffix = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if suffix not in SUPPORTED_DOCUMENT_SUFFIXES:
            raise DocumentStorageError("UNSUPPORTED_DOCUMENT_FORMAT")
        if not content:
            raise DocumentStorageError("EMPTY_DOCUMENT")
        if len(content) > self.max_size_bytes:
            raise DocumentStorageError("DOCUMENT_TOO_LARGE")
        if not case_id or not application_id or not document_id:
            raise DocumentStorageError("CASE_DOCUMENT_ID_REQUIRED")
        checksum = "sha256:" + hashlib.sha256(content).hexdigest()
        record = StoredDocument(
            case_id=case_id,
            application_id=application_id,
            document_id=document_id,
            file_name=file_name,
            content_type=content_type,
            checksum=checksum,
            size_bytes=len(content),
            created_at=datetime.now(timezone.utc),
        )
        key = (case_id, document_id)
        self._metadata[key] = record
        self._content[key] = bytes(content)
        return record

    def get(self, *, case_id: str, application_id: str, document_id: str) -> bytes:
        key = (case_id, document_id)
        record = self._metadata.get(key)
        if record is None or record.application_id != application_id:
            raise DocumentStorageError("DOCUMENT_NOT_FOUND_FOR_CASE")
        return self._content[key]

    def list(self, *, case_id: str, application_id: str) -> list[StoredDocument]:
        return [
            record
            for record in self._metadata.values()
            if record.case_id == case_id and record.application_id == application_id
        ]
