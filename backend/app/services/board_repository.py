from __future__ import annotations

from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.tier2_board.shared_board import (
    SharedBoardConflictError,
    SharedBoardNotFoundError,
    SharedBoardRepository,
)
from app.db.models import DebateLog as DebateLogModel
from app.db.models import SharedBoard as SharedBoardModel
from app.schemas import (
    AgentID,
    BoardStatus,
    DebateIssue,
    DebateRecord,
    DebateStatus,
    MissingDataRequest,
    RiskSeverity,
    SharedBoardState,
    SpecialistAssessment,
    TaskState,
)


_ASSESSMENT_ADAPTER = TypeAdapter(SpecialistAssessment)


class SqlSharedBoardRepository(SharedBoardRepository):
    """SQLAlchemy persistence adapter with pessimistic + optimistic protection."""

    def __init__(
        self,
        db: Session,
        *,
        workflow_id: str,
        workflow_version: str,
    ) -> None:
        self._db = db
        self._workflow_id = workflow_id
        self._workflow_version = workflow_version

    def get_by_case_id(self, case_id: UUID) -> SharedBoardState | None:
        model = self._db.scalar(
            select(SharedBoardModel).where(SharedBoardModel.case_id == case_id)
        )
        return self._to_state(model) if model is not None else None

    def create(self, board: SharedBoardState) -> SharedBoardState:
        existing = self._db.scalar(
            select(SharedBoardModel.id).where(
                SharedBoardModel.case_id == board.case_id
            )
        )
        if existing is not None:
            raise SharedBoardConflictError(
                f"A Shared Board already exists for case {board.case_id}"
            )
        model = SharedBoardModel(
            id=board.board_id,
            case_id=board.case_id,
            workflow_id=self._workflow_id,
            workflow_version=self._workflow_version,
            status=board.status.value,
            task_breakdown=self._serialize_tasks(board),
            specialist_outputs=self._serialize_outputs(board),
            final_summary=board.final_summary,
            missing_data=[item.model_dump(mode="json") for item in board.missing_data],
            consensus_reached=board.consensus_reached,
            current_debate_round=board.current_debate_round,
            review_cycle=board.review_cycle,
            max_debate_rounds=board.max_debate_rounds,
            version=0,
        )
        self._db.add(model)
        self._db.flush()
        return self._to_state(model)

    def save(
        self,
        board: SharedBoardState,
        *,
        expected_version: int,
    ) -> SharedBoardState:
        model = self._db.scalar(
            select(SharedBoardModel)
            .where(SharedBoardModel.case_id == board.case_id)
            .with_for_update()
        )
        if model is None:
            raise SharedBoardNotFoundError(
                f"No Shared Board exists for case {board.case_id}"
            )
        if model.id != board.board_id:
            raise SharedBoardConflictError("Board identity does not match")
        if model.version != expected_version or board.version != expected_version:
            raise SharedBoardConflictError(
                f"Expected board version {expected_version}, found {model.version}"
            )

        model.status = board.status.value
        model.task_breakdown = self._serialize_tasks(board)
        model.specialist_outputs = self._serialize_outputs(board)
        model.final_summary = board.final_summary
        model.missing_data = [
            item.model_dump(mode="json") for item in board.missing_data
        ]
        model.consensus_reached = board.consensus_reached
        model.current_debate_round = board.current_debate_round
        model.max_debate_rounds = board.max_debate_rounds
        model.version = expected_version + 1
        self._sync_debate_log(board)
        self._db.flush()
        return self._to_state(model)

    def reset_for_reassessment(
        self,
        case_id: UUID,
        *,
        tasks: list[TaskState],
        max_debate_rounds: int,
    ) -> SharedBoardState:
        """Start a new review cycle while audit logs preserve the previous history."""

        model = self._db.scalar(
            select(SharedBoardModel)
            .where(SharedBoardModel.case_id == case_id)
            .with_for_update()
        )
        if model is None:
            raise SharedBoardNotFoundError(
                f"No Shared Board exists for case {case_id}"
            )
        model.status = BoardStatus.INITIALIZED.value
        model.task_breakdown = {
            task.task_id: task.model_dump(mode="json") for task in tasks
        }
        model.specialist_outputs = {}
        model.final_summary = None
        model.missing_data = []
        model.consensus_reached = False
        model.current_debate_round = 0
        model.review_cycle += 1
        model.max_debate_rounds = max_debate_rounds
        model.version += 1
        self._db.flush()
        return self._to_state(model)

    def _to_state(self, model: SharedBoardModel) -> SharedBoardState:
        task_values = {
            key: TaskState.model_validate(value)
            for key, value in model.task_breakdown.items()
        }
        output_values = {
            AgentID(key): _ASSESSMENT_ADAPTER.validate_python(value)
            for key, value in model.specialist_outputs.items()
        }
        debate_models = self._db.scalars(
            select(DebateLogModel)
            .where(
                DebateLogModel.case_id == model.case_id,
                DebateLogModel.review_cycle == model.review_cycle,
            )
            .order_by(DebateLogModel.round_number, DebateLogModel.logged_at)
        ).all()
        debate_records = [self._to_debate_record(item) for item in debate_models]
        return SharedBoardState(
            board_id=model.id,
            case_id=model.case_id,
            status=BoardStatus(model.status),
            version=model.version,
            tasks=task_values,
            specialist_outputs=output_values,
            debate_log=debate_records,
            missing_data=[
                MissingDataRequest.model_validate(item)
                for item in model.missing_data
            ],
            final_summary=model.final_summary,
            consensus_reached=model.consensus_reached,
            current_debate_round=model.current_debate_round,
            review_cycle=model.review_cycle,
            max_debate_rounds=model.max_debate_rounds,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _serialize_tasks(board: SharedBoardState) -> dict[str, object]:
        return {
            key: task.model_dump(mode="json") for key, task in board.tasks.items()
        }

    @staticmethod
    def _serialize_outputs(board: SharedBoardState) -> dict[str, object]:
        return {
            key.value: assessment.model_dump(mode="json")
            for key, assessment in board.specialist_outputs.items()
        }

    def _sync_debate_log(self, board: SharedBoardState) -> None:
        existing_models = self._db.scalars(
            select(DebateLogModel).where(
                DebateLogModel.case_id == board.case_id,
                DebateLogModel.review_cycle == board.review_cycle,
            )
        ).all()
        existing = {
            (
                item.review_cycle,
                item.round_number,
                item.issue_code,
                item.target_agent,
            ): item
            for item in existing_models
        }
        for record in board.debate_log:
            key = (
                board.review_cycle,
                record.round_number,
                record.issue.code,
                record.issue.target_agent.value,
            )
            model = existing.get(key)
            if model is None:
                model = DebateLogModel(
                    case_id=board.case_id,
                    review_cycle=board.review_cycle,
                    round_number=record.round_number,
                    critic_agent=record.critic_agent.value,
                    target_agent=record.issue.target_agent.value,
                    issue_code=record.issue.code,
                    severity=record.issue.severity.value,
                    related_field=record.issue.related_field,
                    error_identified=record.issue.description,
                    required_action=record.issue.required_action,
                    specialist_response=record.specialist_response,
                    resolution_applied=record.resolution,
                    status=record.status.value,
                    logged_at=record.logged_at,
                    resolved_at=record.resolved_at,
                )
                self._db.add(model)
                existing[key] = model
            else:
                model.specialist_response = record.specialist_response
                model.resolution_applied = record.resolution
                model.status = record.status.value
                model.resolved_at = record.resolved_at

    @staticmethod
    def _to_debate_record(model: DebateLogModel) -> DebateRecord:
        return DebateRecord(
            round_number=model.round_number,
            issue=DebateIssue(
                code=model.issue_code,
                severity=RiskSeverity(model.severity),
                target_agent=AgentID(model.target_agent),
                description=model.error_identified,
                required_action=model.required_action,
                related_field=model.related_field,
            ),
            status=DebateStatus(model.status),
            specialist_response=model.specialist_response,
            resolution=model.resolution_applied,
            logged_at=model.logged_at,
            resolved_at=model.resolved_at,
        )
