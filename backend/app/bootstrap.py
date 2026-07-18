from __future__ import annotations

import io
import json
from dataclasses import asdict

from app.config import get_settings
from app.db.bootstrap import bootstrap_database
from app.db.session import session_scope
from app.services.assessment_runtime import reconcile_orphaned_runs
from app.services.rag import create_embedding_provider
from app.services.storage import create_object_storage


def bootstrap_runtime() -> dict[str, object]:
    """Initialize buckets and idempotent reference data after Alembic migration."""

    settings = get_settings()
    storage = create_object_storage(settings)
    storage.ensure_buckets()

    hhb_policy_content: str | None = None
    hhb_source_object_key = "policies/hhb/QD-HHB-2026-01.txt"
    if settings.seed_hhb_policy:
        policy_payload = settings.hhb_policy_path.read_bytes()
        hhb_policy_content = policy_payload.decode("utf-8")
        storage.put(
            bucket=settings.minio_policy_bucket,
            object_key=hhb_source_object_key,
            data=io.BytesIO(policy_payload),
            size_bytes=len(policy_payload),
            content_type="text/plain; charset=utf-8",
        )

    demo_case_document_content: str | None = None
    demo_case_document_object_key = "cases/demo/minh-an-credit-dossier.txt"
    if settings.seed_demo_case:
        demo_payload = settings.demo_case_document_path.read_bytes()
        demo_case_document_content = demo_payload.decode("utf-8")
        storage.put(
            bucket=settings.minio_case_bucket,
            object_key=demo_case_document_object_key,
            data=io.BytesIO(demo_payload),
            size_bytes=len(demo_payload),
            content_type="text/plain; charset=utf-8",
        )

    embedding_provider = (
        create_embedding_provider(settings)
        if settings.seed_demo_policies or settings.seed_hhb_policy
        else None
    )
    with session_scope() as db:
        result = bootstrap_database(
            db,
            include_demo_policies=settings.seed_demo_policies,
            include_demo_case=settings.seed_demo_case,
            hhb_policy_content=hhb_policy_content,
            hhb_source_object_key=hhb_source_object_key,
            demo_case_document_content=demo_case_document_content,
            demo_case_document_object_key=demo_case_document_object_key,
            embedding_provider=embedding_provider,
        )
    with session_scope() as db:
        orphaned_runs_recovered = reconcile_orphaned_runs(db)
    return {
        "storage": "ready",
        "database": asdict(result),
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "hhb_policy_seeded": settings.seed_hhb_policy,
        "orphaned_runs_recovered": orphaned_runs_recovered,
    }


def main() -> None:
    print(json.dumps(bootstrap_runtime(), sort_keys=True))


if __name__ == "__main__":
    main()
