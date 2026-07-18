from __future__ import annotations

import io
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentOfficer, ObjectStorageDependency
from app.config import get_settings
from app.db.models import (
    AuditOutcome,
    Case,
    CaseStatus,
    Document,
    DocumentStatus,
)
from app.db.session import get_db
from app.schemas.api import (
    CaseCreateRequest,
    CaseDetailResponse,
    CaseSummaryResponse,
    DocumentResponse,
)
from app.services.audit import write_audit_log
from app.services.document_parser import DocumentValidationError, parse_document
from app.services.storage import case_document_key


router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseDetailResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    request: CaseCreateRequest,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> CaseDetailResponse:
    case = Case(
        company_name=request.company_name,
        requested_amount=request.requested_amount,
        currency=request.currency,
        status=CaseStatus.INGESTED.value,
        workflow_id="corporate_loan_v1",
        workflow_version="1.0",
        input_payload=request.input_payload,
    )
    db.add(case)
    db.flush()
    write_audit_log(
        db,
        case_id=case.id,
        actor_type="HUMAN",
        actor_id=officer.officer_id,
        action="CASE_CREATED",
        entity_type="case",
        entity_id=str(case.id),
        response={"status": case.status},
    )
    db.commit()
    db.refresh(case)
    return _case_detail(case, [])


@router.get("", response_model=list[CaseSummaryResponse])
def list_cases(
    officer: CurrentOfficer,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[CaseSummaryResponse]:
    del officer
    cases = db.scalars(
        select(Case)
        .order_by(Case.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [_case_summary(case) for case in cases]


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(
    case_id: UUID,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> CaseDetailResponse:
    del officer
    case = _get_case_or_404(db, case_id)
    documents = db.scalars(
        select(Document)
        .where(Document.case_id == case_id)
        .order_by(Document.created_at)
    ).all()
    return _case_detail(case, documents)


@router.get("/{case_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    case_id: UUID,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    del officer
    _get_case_or_404(db, case_id)
    documents = db.scalars(
        select(Document)
        .where(Document.case_id == case_id)
        .order_by(Document.created_at)
    ).all()
    return [_document_response(document) for document in documents]


@router.post(
    "/{case_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    case_id: UUID,
    officer: CurrentOfficer,
    storage: ObjectStorageDependency,
    file: UploadFile = File(...),
    document_type: str = Form(default="OTHER"),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    settings = get_settings()
    case = _get_case_or_404(db, case_id)
    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type not in settings.allowed_upload_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported document content type",
        )
    payload = await file.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Document exceeds the configured upload limit",
        )
    try:
        parsed = parse_document(payload, content_type)
    except DocumentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    document_id = uuid4()
    original_filename = file.filename or "document"
    object_key = case_document_key(
        str(case_id),
        str(document_id),
        original_filename,
    )
    storage.put(
        bucket=settings.minio_case_bucket,
        object_key=object_key,
        data=io.BytesIO(payload),
        size_bytes=len(payload),
        content_type=content_type,
    )
    document = Document(
        id=document_id,
        case_id=case_id,
        document_type=document_type.strip().upper()[:100] or "OTHER",
        original_filename=original_filename,
        object_key=object_key,
        content_type=content_type,
        byte_size=len(payload),
        sha256=parsed.sha256,
        extracted_text=parsed.extracted_text[:200_000] or None,
        status=DocumentStatus.PARSED.value,
    )
    db.add(document)
    if parsed.structured_payload is not None:
        case.input_payload = _deep_merge(
            dict(case.input_payload),
            parsed.structured_payload,
        )
    write_audit_log(
        db,
        case_id=case_id,
        actor_type="HUMAN",
        actor_id=officer.officer_id,
        action="DOCUMENT_UPLOADED",
        entity_type="document",
        entity_id=str(document.id),
        outcome=AuditOutcome.SUCCEEDED,
        request={
            "filename": original_filename,
            "content_type": content_type,
            "byte_size": len(payload),
            "sha256": parsed.sha256,
        },
        response={"object_key": object_key, "status": document.status},
    )
    db.commit()
    db.refresh(document)
    return _document_response(document)


@router.get("/{case_id}/documents/{document_id}/download")
def get_document_download(
    case_id: UUID,
    document_id: UUID,
    officer: CurrentOfficer,
    storage: ObjectStorageDependency,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    del officer
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.case_id == case_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {
        "url": storage.presigned_get_url(
            bucket=get_settings().minio_case_bucket,
            object_key=document.object_key,
            expires=timedelta(minutes=15),
        )
    }


def _get_case_or_404(db: Session, case_id: UUID) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


def _case_summary(case: Case) -> CaseSummaryResponse:
    return CaseSummaryResponse(
        id=case.id,
        company_name=case.company_name,
        requested_amount=case.requested_amount,
        currency=case.currency,
        status=case.status,
        workflow_id=case.workflow_id,
        workflow_version=case.workflow_version,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _case_detail(
    case: Case,
    documents: list[Document],
) -> CaseDetailResponse:
    return CaseDetailResponse(
        **_case_summary(case).model_dump(),
        input_payload=case.input_payload,
        documents=[_document_response(document) for document in documents],
    )


def _document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        case_id=document.case_id,
        document_type=document.document_type,
        original_filename=document.original_filename,
        content_type=document.content_type,
        byte_size=document.byte_size,
        sha256=document.sha256,
        status=document.status,
        created_at=document.created_at,
    )


def _deep_merge(
    current: dict[str, object],
    update: dict[str, object],
) -> dict[str, object]:
    result = dict(current)
    for key, value in update.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = _deep_merge(
                {str(nested_key): nested_value for nested_key, nested_value in existing.items()},
                {str(nested_key): nested_value for nested_key, nested_value in value.items()},
            )
        else:
            result[key] = value
    return result
