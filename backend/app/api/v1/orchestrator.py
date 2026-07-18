from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.tier1_orchestrator.deep_agent import (
    CaseNotAssessableError,
    DeepAgentOrchestrator,
)
from app.api.dependencies import CurrentOfficer
from app.db.models import Case
from app.db.session import get_db
from app.schemas import DebateRecord, SharedBoardState
from app.schemas.api import AssessmentStartResponse
from app.services.board_repository import SqlSharedBoardRepository
from app.services.llm import LLMGenerationError


router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


@router.post(
    "/cases/{case_id}/assessment",
    response_model=AssessmentStartResponse,
)
def start_assessment(
    case_id: UUID,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> AssessmentStartResponse:
    """Run the real LLM-backed graph and stop at the human verification gate."""

    del officer  # Authentication is enforced at the boundary; agents own the audit rows.
    try:
        board = DeepAgentOrchestrator(db).run(case_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        ) from exc
    except CaseNotAssessableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (LLMGenerationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider could not complete the structured assessment",
        ) from exc

    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    return AssessmentStartResponse(case_id=case.id, status=case.status, board=board)


@router.get(
    "/cases/{case_id}/shared-board",
    response_model=SharedBoardState,
)
def get_shared_board(
    case_id: UUID,
    officer: CurrentOfficer,
    db: Session = Depends(get_db),
) -> SharedBoardState:
    del officer
    case = _case_or_404(db, case_id)
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
    del officer
    case = _case_or_404(db, case_id)
    board = _repository(db, case).get_by_case_id(case_id)
    if board is None:
        return []
    return board.debate_log


def _case_or_404(db: Session, case_id: UUID) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    return case


def _repository(db: Session, case: Case) -> SqlSharedBoardRepository:
    return SqlSharedBoardRepository(
        db,
        workflow_id=case.workflow_id,
        workflow_version=case.workflow_version,
    )
