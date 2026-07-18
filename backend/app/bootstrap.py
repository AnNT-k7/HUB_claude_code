from __future__ import annotations

import json
from dataclasses import asdict

from app.config import get_settings
from app.db.bootstrap import bootstrap_database
from app.db.session import session_scope
from app.services.rag import create_embedding_provider
from app.services.storage import create_object_storage


def bootstrap_runtime() -> dict[str, object]:
    """Initialize buckets and idempotent reference data after Alembic migration."""

    settings = get_settings()
    storage = create_object_storage(settings)
    storage.ensure_buckets()

    embedding_provider = (
        create_embedding_provider(settings) if settings.seed_demo_policies else None
    )
    with session_scope() as db:
        result = bootstrap_database(
            db,
            include_demo_policies=settings.seed_demo_policies,
            include_demo_case=settings.seed_demo_case,
            embedding_provider=embedding_provider,
        )
    return {
        "storage": "ready",
        "database": asdict(result),
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
    }


def main() -> None:
    print(json.dumps(bootstrap_runtime(), sort_keys=True))


if __name__ == "__main__":
    main()
