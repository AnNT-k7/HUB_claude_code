"""SQLite-by-default engine/session for the case-management persistence
layer (``app/db/case_models.py``). Independent of ``app/db/session.py``,
which targets the Postgres/pgvector production deployment and is not
required to run this MVP."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.case_models import CaseBase

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve_database_url(raw_url: str) -> str:
    """A relative ``sqlite:///./data/...`` URL must not depend on the
    process's current working directory (uvicorn launched from the repo
    root vs. from ``backend/`` would otherwise silently create two
    different database files). Anchor relative sqlite paths to the backend
    package root; leave absolute paths and non-sqlite URLs untouched."""

    if not raw_url.startswith("sqlite:///"):
        return raw_url
    path_part = raw_url.removeprefix("sqlite:///")
    if path_part == ":memory:" or path_part.startswith("/"):
        return raw_url
    absolute_path = (BACKEND_ROOT / path_part).resolve()
    return f"sqlite:///{absolute_path}"


_settings = get_settings()
_database_url = _resolve_database_url(_settings.database_url)
_connect_args = {"check_same_thread": False} if _database_url.startswith("sqlite") else {}

if _database_url.startswith("sqlite:///"):
    _db_path = _database_url.removeprefix("sqlite:///")
    if _db_path != ":memory:":
        Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

case_engine = create_engine(_database_url, connect_args=_connect_args)
CaseSessionLocal = sessionmaker(bind=case_engine, autoflush=False, autocommit=False)


def init_case_db() -> None:
    """Create tables if they don't exist yet. Safe to call on every startup."""

    CaseBase.metadata.create_all(bind=case_engine)


def get_case_db() -> Session:
    return CaseSessionLocal()
