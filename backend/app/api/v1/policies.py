from __future__ import annotations

import io
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import ObjectStorageDependency, PolicyAdmin
from app.config import get_settings
from app.db.session import get_db
from app.schemas import AgentID, SPECIALIST_AGENT_IDS
from app.schemas.api import PolicyIngestionResponse
from app.services.document_parser import DocumentValidationError, parse_document
from app.services.rag import (
    AGENT_KNOWLEDGE_KEYS,
    PolicyIngestionService,
    create_embedding_provider,
)
from app.services.storage import policy_document_key


router = APIRouter(prefix="/policies", tags=["policies"])


@router.post(
    "/documents",
    response_model=PolicyIngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_policy_document(
    officer: PolicyAdmin,
    storage: ObjectStorageDependency,
    file: UploadFile = File(...),
    agent_id: AgentID = Form(...),
    title: str = Form(..., min_length=1, max_length=512),
    version: str = Form(..., min_length=1, max_length=50),
    section_id: str = Form(default="UNSPECIFIED", max_length=255),
    page_number: int = Form(default=1, ge=1),
    effective_at: datetime | None = Form(default=None),
    db: Session = Depends(get_db),
) -> PolicyIngestionResponse:
    """Embed an anonymized bank policy into exactly one specialist's RAG scope."""

    del officer  # Authorization is enforced by the PolicyAdmin dependency.
    if agent_id not in SPECIALIST_AGENT_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Policies can only be assigned to a Tier-2 specialist",
        )

    settings = get_settings()
    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type not in settings.allowed_upload_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported policy content type",
        )
    payload = await file.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Policy exceeds the configured upload limit",
        )
    try:
        parsed = parse_document(payload, content_type)
    except DocumentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    filename = file.filename or "policy"
    object_key = policy_document_key(
        AGENT_KNOWLEDGE_KEYS[agent_id],
        str(uuid4()),
        filename,
    )
    try:
        result = PolicyIngestionService(
            db,
            create_embedding_provider(settings),
        ).ingest(
            agent_id=agent_id,
            title=title.strip(),
            version=version.strip(),
            content=parsed.extracted_text,
            source_sha256=parsed.sha256,
            source_object_key=object_key,
            section_id=section_id.strip() or "UNSPECIFIED",
            page_number=page_number,
            effective_at=effective_at,
        )
        storage.put(
            bucket=settings.minio_policy_bucket,
            object_key=object_key,
            data=io.BytesIO(payload),
            size_bytes=len(payload),
            content_type=content_type,
        )
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent knowledge bases have not been bootstrapped",
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return PolicyIngestionResponse(
        policy_document_id=result.policy_document_id,
        chunks_created=result.chunks_created,
        duplicate_chunks=result.duplicate_chunks,
    )
