from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentOfficer, require_case_access
from app.db.models import AssessmentEvent, AssessmentRun, Case
from app.db.session import SessionLocal, get_db
from app.schemas import AgentID, DebateRecord, SharedBoardState
from app.schemas.api import (
    AssessmentEventResponse,
    AssessmentRunResponse,
    AssessmentRuntimeResponse,
    AssessmentStartResponse,
)
from app.services.assessment_runtime import (
    AssessmentRunConflict,
    create_assessment_run,
    execute_assessment_run,
    latest_run,
    queue_resume,
    request_stop,
)
from app.services.audit import write_audit_log
from app.services.board_repository import SqlSharedBoardRepository


router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


@router.post(
    "/cases/{case_id}/assessment",
    response_model=AssessmentStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_assessment(
    case_id: UUID,
    background_tasks: BackgroundTasks,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> AssessmentStartResponse:
    """Queue the real LLM-backed graph and return immediately for live UI updates."""

    case = _case_or_404(db, case_id)
    require_case_access(case.created_by, officer)
    try:
        run = create_assessment_run(
            db,
            case=case,
            started_by=officer.officer_id,
        )
    except AssessmentRunConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    write_audit_log(
        db,
        case_id=case_id,
        actor_type="HUMAN",
        actor_id=officer.officer_id,
        action="ASSESSMENT_REQUESTED",
        entity_type="case",
        entity_id=str(case_id),
        request={"orchestrator": AgentID.BANKING_ORCHESTRATOR.value},
    )
    db.commit()
    background_tasks.add_task(execute_assessment_run, run.id)
    return AssessmentStartResponse(
        case_id=case.id,
        status=run.status,
        run=_run_response(run),
    )


@router.post(
    "/cases/{case_id}/assessment/stop",
    response_model=AssessmentRunResponse,
)
def stop_assessment(
    case_id: UUID,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> AssessmentRunResponse:
    case = _case_or_404(db, case_id)
    require_case_access(case.created_by, officer)
    run = latest_run(db, case_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Assessment run not found")
    try:
        updated = request_stop(db, run)
    except AssessmentRunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _run_response(updated)


@router.post(
    "/cases/{case_id}/assessment/resume",
    response_model=AssessmentStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def resume_assessment(
    case_id: UUID,
    background_tasks: BackgroundTasks,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> AssessmentStartResponse:
    case = _case_or_404(db, case_id)
    require_case_access(case.created_by, officer)
    try:
        run = queue_resume(db, case=case, started_by=officer.officer_id)
    except AssessmentRunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(execute_assessment_run, run.id)
    return AssessmentStartResponse(
        case_id=case.id,
        status=run.status,
        run=_run_response(run),
    )


@router.get(
    "/cases/{case_id}/assessment/runtime",
    response_model=AssessmentRuntimeResponse,
)
def get_assessment_runtime(
    case_id: UUID,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> AssessmentRuntimeResponse:
    case = _case_or_404(db, case_id)
    require_case_access(case.created_by, officer)
    run = latest_run(db, case_id)
    if run is None:
        return AssessmentRuntimeResponse()
    events = db.scalars(
        select(AssessmentEvent)
        .where(AssessmentEvent.run_id == run.id)
        .order_by(AssessmentEvent.id.desc())
        .limit(200)
    ).all()
    return AssessmentRuntimeResponse(
        run=_run_response(run),
        events=[_event_response(item) for item in reversed(events)],
    )


@router.get("/cases/{case_id}/events/stream")
async def stream_assessment_events(
    case_id: UUID,
    officer: CurrentOfficer,
    after: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    case = _case_or_404(db, case_id)
    require_case_access(case.created_by, officer)

    async def event_stream() -> AsyncIterator[str]:
        cursor = after
        quiet_ticks = 0
        while True:
            stream_db = SessionLocal()
            try:
                run = latest_run(stream_db, case_id)
                events = stream_db.scalars(
                    select(AssessmentEvent)
                    .where(
                        AssessmentEvent.case_id == case_id,
                        AssessmentEvent.id > cursor,
                    )
                    .order_by(AssessmentEvent.id)
                    .limit(100)
                ).all()
                terminal = run is None or run.status in {
                    "PAUSED",
                    "COMPLETED",
                    "FAILED",
                }
            finally:
                stream_db.close()
            if events:
                quiet_ticks = 0
                for event in events:
                    cursor = event.id
                    payload = _event_response(event).model_dump(mode="json")
                    yield (
                        f"id: {event.id}\n"
                        f"event: assessment\n"
                        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    )
            else:
                quiet_ticks += 1
                if quiet_ticks % 20 == 0:
                    yield ": keep-alive\n\n"
                if terminal:
                    break
            await asyncio.sleep(0.75)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/cases/{case_id}/shared-board",
    response_model=SharedBoardState,
)
def get_shared_board(
    case_id: UUID,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> SharedBoardState:
    case = _case_or_404(db, case_id)
    require_case_access(case.created_by, officer)
    board = _repository(db, case).get_by_case_id(case_id)
    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment has not initialized a Shared Board",
        )
    return board


@router.get(
    "/cases/{case_id}/debates",
    response_model=list[DebateRecord],
)
def get_debates(
    case_id: UUID,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> list[DebateRecord]:
    case = _case_or_404(db, case_id)
    require_case_access(case.created_by, officer)
    board = _repository(db, case).get_by_case_id(case_id)
    return [] if board is None else board.debate_log


def _case_or_404(db: Session, case_id: UUID) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _repository(db: Session, case: Case) -> SqlSharedBoardRepository:
    return SqlSharedBoardRepository(
        db,
        workflow_id=case.workflow_id,
        workflow_version=case.workflow_version,
    )


def _run_response(run: AssessmentRun) -> AssessmentRunResponse:
    return AssessmentRunResponse(
        id=run.id,
        case_id=run.case_id,
        status=run.status,
        current_stage=run.current_stage,
        checkpoint_stage=run.checkpoint_stage,
        stop_requested=run.stop_requested,
        started_by=run.started_by,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


def _event_response(event: AssessmentEvent) -> AssessmentEventResponse:
    return AssessmentEventResponse(
        id=event.id,
        run_id=event.run_id,
        case_id=event.case_id,
        event_type=event.event_type,
        stage=event.stage,
        agent_id=event.agent_id,
        status=event.status,
        title=event.title,
        message=event.message,
        evidence=event.evidence,
        created_at=event.created_at,
    )
