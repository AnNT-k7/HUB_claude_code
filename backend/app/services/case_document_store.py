"""Disk-backed, case-scoped storage for uploaded documents.

Supersedes the in-memory ``CaseScopedDocumentStore`` in ``app/services/
storage.py`` for the multi-case runtime: uploaded files must survive a
process restart ("reload trang không làm mất dữ liệu"). Kept as a thin,
swappable adapter — the docstring on the original class already flagged
MinIO as the intended production replacement; this local-disk version is the
pragmatic MVP middle ground the plan calls out as an explicit scope cut.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.config import get_settings
from app.db.case_session import BACKEND_ROOT, _resolve_database_url

SUPPORTED_DOCUMENT_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".md", ".txt", ".csv"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class DocumentStorageError(ValueError):
    """Raised for invalid file metadata, unsupported formats, or oversize
    uploads. Caller (the API layer) turns this into a 4xx response."""


def _case_root() -> Path:
    settings = get_settings()
    # Mirror app/db/case_session.py's path resolution exactly so uploaded
    # files always land next to the SQLite DB that references them,
    # regardless of the process's current working directory at startup.
    database_url = _resolve_database_url(settings.database_url)
    if database_url.startswith("sqlite:///") and database_url != "sqlite:///:memory:":
        db_path = Path(database_url.removeprefix("sqlite:///"))
        root = db_path.parent / "case_documents"
    else:
        root = BACKEND_ROOT / "data" / "case_documents"
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_upload(*, case_id: str, document_id: str, file_name: str, content: bytes) -> tuple[Path, str]:
    """Write bytes to disk under a case-scoped directory. Returns (path, checksum)."""

    suffix = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if suffix not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise DocumentStorageError(
            f"UNSUPPORTED_DOCUMENT_FORMAT:{suffix or 'none'}"
        )
    if not content:
        raise DocumentStorageError("EMPTY_DOCUMENT")
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentStorageError("DOCUMENT_TOO_LARGE")
    if not case_id or not document_id:
        raise DocumentStorageError("CASE_DOCUMENT_ID_REQUIRED")

    case_dir = _case_root() / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{document_id}__{Path(file_name).name}"
    path = case_dir / safe_name
    path.write_bytes(content)
    checksum = "sha256:" + hashlib.sha256(content).hexdigest()
    return path, checksum


def read_document(*, case_id: str, storage_path: str) -> bytes:
    path = Path(storage_path)
    if not path.is_file() or _case_root() not in path.resolve().parents:
        raise DocumentStorageError("DOCUMENT_NOT_FOUND_FOR_CASE")
    return path.read_bytes()
