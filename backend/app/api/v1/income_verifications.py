"""HTTP API for persistent multi-case income verification."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.agents.income_verification.human_review import HumanReviewError
from app.agents.income_verification.state import CaseContext
from app.services.case_repository import (
    CaseNotFound,
    CaseRepositoryError,
    DocumentNotFound,
)
from app.services.runtime import (
    IncomeVerificationRuntime,
    RuntimeCaseNotFound,
    UnsupportedDemoApplication,
    get_runtime,
)

from .schemas import (
    AuditListResponse,
    CaseDetailResponse,
    CaseListResponse,
    CaseSummaryResponse,
    CreateCaseRequest,
    DocumentResponse,
    EvidenceListResponse,
    ResetResponse,
    ReviewRequest,
    ReviewResponse,
    RuntimeInfoResponse,
    StartWorkflowRequest,
    StartWorkflowResponse,
)


router = APIRouter(tags=["Income Verification"])


def require_underwriter(
    x_reviewer_id: Annotated[str | None, Header()] = None,
    x_role: Annotated[str | None, Header()] = None,
) -> str:
    if x_role != "UNDERWRITER" or not x_reviewer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Underwriter role and reviewer identity are required.",
        )
    return x_reviewer_id


RuntimeDependency = Annotated[IncomeVerificationRuntime, Depends(get_runtime)]
ReviewerDependency = Annotated[str, Depends(require_underwriter)]


def _document_response(row) -> DocumentResponse:
    return DocumentResponse(
        id=row.id,
        case_id=row.case_id,
        file_name=row.file_name,
        content_type=row.content_type,
        document_type=row.document_type,
        checksum=row.checksum,
        size_bytes=row.size_bytes,
        page_count=row.page_count,
        processing_status=row.processing_status,
        error_message=row.error_message,
        uploaded_at=row.uploaded_at,
    )


def _case_summary(runtime: IncomeVerificationRuntime, row) -> CaseSummaryResponse:
    return CaseSummaryResponse(
        id=row.id,
        application_id=row.application_id,
        customer_name=row.customer_name,
        customer_code=row.customer_code,
        company=row.company,
        requested_amount=row.requested_amount,
        currency=row.currency,
        status=row.status,
        pipeline_status=row.pipeline_status,
        state_version=row.state_version,
        document_count=len(runtime.repository.list_documents(row.id)),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/runtime", response_model=RuntimeInfoResponse)
async def runtime_info(_reviewer_id: ReviewerDependency, runtime: RuntimeDependency) -> RuntimeInfoResponse:
    return RuntimeInfoResponse.model_validate(runtime.runtime_info())


@router.post("/cases", response_model=CaseSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CreateCaseRequest,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> CaseSummaryResponse:
    row = runtime.repository.create_case(**payload.model_dump())
    return _case_summary(runtime, row)


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(_reviewer_id: ReviewerDependency, runtime: RuntimeDependency) -> CaseListResponse:
    items = [_case_summary(runtime, row) for row in runtime.repository.list_cases()]
    return CaseListResponse(items=items, total=len(items))


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> CaseDetailResponse:
    try:
        row = runtime.repository.get_case(case_id)
        documents = runtime.repository.list_documents(case_id)
        context = runtime.repository.load_context(case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    summary = _case_summary(runtime, row)
    return CaseDetailResponse(
        **summary.model_dump(),
        documents=[_document_response(item) for item in documents],
        context=context.model_dump(mode="json") if context else None,
        agent_runs=runtime.repository.list_agent_runs(case_id),
    )


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
    document_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    content = await file.read()
    try:
        row = runtime.repository.add_document(
            case_id=case_id,
            file_name=file.filename or "document",
            content_type=file.content_type or "application/octet-stream",
            document_type=document_type,
            content=content,
        )
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    except CaseRepositoryError as exc:
        code = str(exc)
        http_status = {
            "DOCUMENT_TOO_LARGE": 413,
            "UNSUPPORTED_DOCUMENT_FORMAT": 415,
            "DUPLICATE_DOCUMENT": 409,
        }.get(code, 422)
        raise HTTPException(status_code=http_status, detail=code) from exc
    return _document_response(row)


@router.get("/cases/{case_id}/documents/{document_id}/download")
async def download_document(
    case_id: str,
    document_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
):
    try:
        row = runtime.repository.get_document(case_id, document_id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc
    path = Path(row.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored document not found.")
    return FileResponse(path, media_type=row.content_type, filename=row.file_name)


@router.post("/cases/{case_id}/run", response_model=CaseContext)
async def run_case(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> CaseContext:
    try:
        return await runtime.start_case(case_id, rerun=True)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc


@router.get("/cases/{case_id}/status", response_model=CaseContext)
@router.get("/cases/{case_id}/result", response_model=CaseContext)
async def get_case_result(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> CaseContext:
    try:
        return await runtime.get(case_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc


@router.post(
    "/applications/{application_id}/income-verification",
    response_model=StartWorkflowResponse,
)
async def start_workflow(
    application_id: str,
    _payload: StartWorkflowRequest,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> StartWorkflowResponse:
    try:
        context = await runtime.start(application_id)
    except UnsupportedDemoApplication as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StartWorkflowResponse(case_id=context.case_id, workflow_state=context.workflow_state)


@router.post("/applications/{application_id}/income-verification/reset", response_model=ResetResponse)
async def reset_workflow(
    application_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> ResetResponse:
    try:
        await runtime.reset(application_id)
    except UnsupportedDemoApplication as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ResetResponse(application_id=application_id, status="RESET")


@router.get("/income-verifications/{case_id}", response_model=CaseContext)
async def get_case(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> CaseContext:
    try:
        return await runtime.get(case_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc


@router.post("/income-verifications/{case_id}/review", response_model=ReviewResponse)
async def submit_review(
    case_id: str,
    review: ReviewRequest,
    reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> ReviewResponse:
    try:
        context = await runtime.review(case_id, review, reviewer_id=reviewer_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    except HumanReviewError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewResponse(case_id=case_id, workflow_state=context.workflow_state)


@router.post("/income-verifications/{case_id}/retry-actions", response_model=ReviewResponse)
async def retry_actions(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> ReviewResponse:
    try:
        context = await runtime.retry_actions(case_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewResponse(case_id=case_id, workflow_state=context.workflow_state)


@router.get("/income-verifications/{case_id}/evidence", response_model=EvidenceListResponse)
async def get_evidence(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> EvidenceListResponse:
    try:
        context = await runtime.get(case_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    return EvidenceListResponse(case_id=case_id, evidence=context.evidence)


@router.get("/income-verifications/{case_id}/audit", response_model=AuditListResponse)
async def get_audit(
    case_id: str,
    _reviewer_id: ReviewerDependency,
    runtime: RuntimeDependency,
) -> AuditListResponse:
    try:
        context = await runtime.get(case_id)
    except RuntimeCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found.") from exc
    return AuditListResponse(case_id=case_id, audit_events=context.audit_events)
