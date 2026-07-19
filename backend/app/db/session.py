from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def initialize_mvp_database(bind=None) -> None:
    """Create only the target MVP tables, avoiding legacy PostgreSQL-only types."""

    from app.db.models import (
        AgentResultRecord,
        AgentRunRecord,
        EvidenceRecord,
        FinalReportRecord,
        IncomeAuditLog,
        IncomeCase,
        IncomeDocument,
    )

    selected = [
        IncomeCase.__table__,
        IncomeDocument.__table__,
        AgentRunRecord.__table__,
        AgentResultRecord.__table__,
        EvidenceRecord.__table__,
        FinalReportRecord.__table__,
        IncomeAuditLog.__table__,
    ]
    IncomeCase.metadata.create_all(bind=bind or engine, tables=selected)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
