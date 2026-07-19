"""Multi-case income-verification API: create cases, upload documents, run
the pipeline, and review results — the generalized replacement for the
single-fixed-case endpoints in ``income_verifications.py`` (kept for
backward compatibility with the original demo)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.agents.income_verification.human_review import HumanReviewError
from app.agents.income_verification.state import CaseContext
from app.services.case_document_store import DocumentStorageError
from app.services.case_service import CaseNotFoundError, CaseService, get_case_service

from .case_schemas import (
    CaseListResponse,
    CaseStatusResponse,
    CaseSummaryResponse,
    CreateCaseRequest,
    CreateCaseResponse,
    DocumentListResponse,
    DocumentSummaryResponse,
    SystemStatusResponse,
    UploadDocumentResponse,
)
from .income_verifications import require_underwriter
from .schemas import AuditListResponse, EvidenceListResponse, ResetResponse, ReviewRequest, ReviewResponse


router = APIRouter(prefix="/cases", tags=["Case Management"])

CaseServiceDependency = Annotated[CaseService, Depends(get_case_service)]
ReviewerDependency = Annotated[str, Depends(require_underwriter)]


def _summary_to_response(summary) -> CaseSummaryResponse:
    return CaseSummaryResponse(
        case_id=summary.case_id,
        application_id=summary.application_id,
        customer_name=summary.customer_name,
        employer=summary.employer,
        requested_amount=summary.requested_amount,
        loan_term_months=summary.loan_term_months,
        workflow_state=summary.workflow_state,
        verification_status=summary.verification_status,
        document_count=summary.document_count,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


def _document_to_response(doc) -> DocumentSummaryResponse:
    return DocumentSummaryResponse(
        document_id=doc.document_id,
        file_name=doc.file_name,
        content_type=doc.content_type,
        document_type=doc.document_type,
        classification_method=doc.classification_method,
        checksum=doc.checksum,
        size_bytes=doc.size_bytes,
        parse_status=doc.parse_status,
        uploaded_at=doc.uploaded_at,
    )


@router.post("", response_model=CreateCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CreateCaseRequest,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> CreateCaseResponse:
    context = await service.create_case(
        customer_name=payload.customer_name,
        customer_code=payload.customer_code,
        employer=payload.employer,
        requested_amount=payload.requested_amount,
        loan_term_months=payload.loan_term_months,
    )
    return CreateCaseResponse(
        case_id=context.case_id,
        application_id=context.application_id,
        workflow_state=context.workflow_state,
    )


@router.get("", response_model=CaseListResponse)
async def list_cases(
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> CaseListResponse:
    summaries = await service.list_cases()
    return CaseListResponse(cases=[_summary_to_response(s) for s in summaries])


@router.get("/system/status", response_model=SystemStatusResponse)
async def system_status(
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> SystemStatusResponse:
    """Registered before the /{case_id} routes so "system" is never captured
    as a case_id path parameter."""

    return SystemStatusResponse(llm_mode=service.llm.mode_label, rag_mode=service.rag_mode)


@router.get("/{case_id}", response_model=CaseContext)
async def get_case(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> CaseContext:
    try:
        return await service.get_case(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc


@router.get("/{case_id}/status", response_model=CaseStatusResponse)
async def get_case_status(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> CaseStatusResponse:
    try:
        context = await service.get_case(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    return CaseStatusResponse(
        case_id=context.case_id,
        workflow_state=context.workflow_state,
        state_version=context.state_version,
        updated_at=context.updated_at,
    )


@router.post("/{case_id}/documents", response_model=UploadDocumentResponse)
async def upload_document(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
    file: UploadFile = File(...),
    document_type_hint: str | None = Form(default=None),
) -> UploadDocumentResponse:
    raw_bytes = await file.read()
    try:
        summary = await service.add_document(
            case_id,
            file_name=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            raw_bytes=raw_bytes,
            document_type_hint=document_type_hint,
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    except DocumentStorageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UploadDocumentResponse(document=_document_to_response(summary))


@router.get("/{case_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> DocumentListResponse:
    try:
        await service.get_case(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    docs = await service.list_documents(case_id)
    return DocumentListResponse(case_id=case_id, documents=[_document_to_response(d) for d in docs])


@router.get("/{case_id}/documents/{document_id}/download")
async def download_document(
    case_id: str,
    document_id: str,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> Response:
    try:
        raw_bytes, file_name, content_type = await service.get_document_bytes(case_id, document_id)
    except DocumentStorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=raw_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )


@router.post("/{case_id}/run", response_model=CaseContext)
async def run_pipeline(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> CaseContext:
    try:
        return await service.run_pipeline(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc


@router.post("/{case_id}/review", response_model=ReviewResponse)
async def submit_review(
    case_id: str,
    review: ReviewRequest,
    reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> ReviewResponse:
    try:
        context = await service.review(case_id, review, reviewer_id=reviewer_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    except HumanReviewError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewResponse(case_id=case_id, workflow_state=context.workflow_state)


@router.post("/{case_id}/retry-actions", response_model=ReviewResponse)
async def retry_actions(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> ReviewResponse:
    try:
        context = await service.retry_actions(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    return ReviewResponse(case_id=case_id, workflow_state=context.workflow_state)


@router.get("/{case_id}/evidence", response_model=EvidenceListResponse)
async def get_evidence(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> EvidenceListResponse:
    try:
        context = await service.get_case(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    return EvidenceListResponse(case_id=case_id, evidence=context.evidence)


@router.get("/{case_id}/audit", response_model=AuditListResponse)
async def get_audit(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    service: CaseServiceDependency,
) -> AuditListResponse:
    try:
        context = await service.get_case(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    return AuditListResponse(case_id=case_id, audit_events=context.audit_events)
