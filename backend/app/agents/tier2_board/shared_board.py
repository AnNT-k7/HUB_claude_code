"""Typed Shared Board repository boundary and concurrency-safe state manager."""

from collections.abc import Sequence
from threading import RLock
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from app.schemas.enums import (
    AgentID,
    AssessmentStatus,
    BoardStatus,
    DebateStatus,
    SPECIALIST_AGENT_IDS,
    TaskStatus,
)
from app.schemas.tier2 import (
    DebateRecord,
    SharedBoardState,
    SpecialistAssessment,
    TaskState,
    utc_now,
)


class SharedBoardError(RuntimeError):
    """Base error for Shared Board state operations."""


class SharedBoardNotFoundError(SharedBoardError):
    """Raised when a case has no initialized Shared Board."""


class SharedBoardConflictError(SharedBoardError):
    """Raised when optimistic version validation detects a stale write."""


class SharedBoardTransitionError(SharedBoardError):
    """Raised when a requested board transition violates an invariant."""


@runtime_checkable
class SharedBoardRepository(Protocol):
    """Persistence port; DB implementations must enforce optimistic writes."""

    def get_by_case_id(self, case_id: UUID) -> SharedBoardState | None:
        """Return an isolated board snapshot or None."""

    def create(self, board: SharedBoardState) -> SharedBoardState:
        """Persist a new board with version zero."""

    def save(
        self,
        board: SharedBoardState,
        *,
        expected_version: int,
    ) -> SharedBoardState:
        """Atomically persist and increment version when expected_version matches."""


class InMemorySharedBoardRepository:
    """Deterministic repository for unit tests and local graph execution."""

    def __init__(self) -> None:
        self._boards: dict[UUID, SharedBoardState] = {}
        self._lock = RLock()

    def get_by_case_id(self, case_id: UUID) -> SharedBoardState | None:
        with self._lock:
            board = self._boards.get(case_id)
            return board.model_copy(deep=True) if board is not None else None

    def create(self, board: SharedBoardState) -> SharedBoardState:
        with self._lock:
            if board.case_id in self._boards:
                raise SharedBoardConflictError(
                    f"A Shared Board already exists for case {board.case_id}"
                )
            if board.version != 0:
                raise SharedBoardConflictError("A new Shared Board must have version zero")
            stored = board.model_copy(deep=True)
            self._boards[board.case_id] = stored
            return stored.model_copy(deep=True)

    def save(
        self,
        board: SharedBoardState,
        *,
        expected_version: int,
    ) -> SharedBoardState:
        with self._lock:
            current = self._boards.get(board.case_id)
            if current is None:
                raise SharedBoardNotFoundError(
                    f"No Shared Board exists for case {board.case_id}"
                )
            if current.board_id != board.board_id:
                raise SharedBoardConflictError("Board identity does not match stored state")
            if current.version != expected_version or board.version != expected_version:
                raise SharedBoardConflictError(
                    f"Expected board version {expected_version}, found {current.version}"
                )
            stored = board.model_copy(
                update={"version": expected_version + 1, "updated_at": utc_now()},
                deep=True,
            )
            # model_copy does not validate updates; round-trip validation protects the port.
            stored = SharedBoardState.model_validate(stored.model_dump())
            self._boards[board.case_id] = stored
            return stored.model_copy(deep=True)


class SharedBoardManager:
    """The only Tier-2 coordination surface agents should use."""

    def __init__(self, repository: SharedBoardRepository) -> None:
        self._repository = repository

    def initialize(
        self,
        case_id: UUID,
        tasks: Sequence[TaskState],
        *,
        max_debate_rounds: int = 3,
        board_id: UUID | None = None,
    ) -> SharedBoardState:
        task_map = {task.task_id: task for task in tasks}
        if len(task_map) != len(tasks):
            raise SharedBoardTransitionError("Task IDs must be unique")
        board = SharedBoardState(
            board_id=board_id or uuid4(),
            case_id=case_id,
            tasks=task_map,
            max_debate_rounds=max_debate_rounds,
        )
        return self._repository.create(board)

    def get(self, case_id: UUID) -> SharedBoardState:
        board = self._repository.get_by_case_id(case_id)
        if board is None:
            raise SharedBoardNotFoundError(
                f"No Shared Board exists for case {case_id}"
            )
        return board

    def post_assessment(
        self,
        case_id: UUID,
        assessment: SpecialistAssessment,
        *,
        expected_version: int,
    ) -> SharedBoardState:
        board = self._load_for_write(case_id, expected_version)
        if board.consensus_reached:
            raise SharedBoardTransitionError(
                "Cannot post specialist output after consensus is reached"
            )
        outputs = dict(board.specialist_outputs)
        outputs[assessment.agent_id] = assessment
        task_status = _task_status_for_assessment(assessment.status)
        tasks = {
            task_id: (
                task.model_copy(
                    update={
                        "status": task_status,
                        "attempts": task.attempts + 1,
                        "updated_at": utc_now(),
                    }
                )
                if task.assigned_to == assessment.agent_id
                else task
            )
            for task_id, task in board.tasks.items()
        }
        updated = board.model_copy(
            update={
                "specialist_outputs": outputs,
                "tasks": tasks,
                "status": BoardStatus.SPECIALISTS_RUNNING,
                "updated_at": utc_now(),
            },
            deep=True,
        )
        return self._save_validated(updated, expected_version)

    def set_task_status(
        self,
        case_id: UUID,
        task_id: str,
        status: TaskStatus,
        *,
        expected_version: int,
        detail: str = "",
    ) -> SharedBoardState:
        board = self._load_for_write(case_id, expected_version)
        task = board.tasks.get(task_id)
        if task is None:
            raise SharedBoardTransitionError(f"Unknown task ID: {task_id}")
        tasks = dict(board.tasks)
        tasks[task_id] = task.model_copy(
            update={"status": status, "detail": detail, "updated_at": utc_now()}
        )
        updated = board.model_copy(
            update={"tasks": tasks, "updated_at": utc_now()},
            deep=True,
        )
        return self._save_validated(updated, expected_version)

    def append_debate_round(
        self,
        case_id: UUID,
        records: Sequence[DebateRecord],
        *,
        expected_version: int,
    ) -> SharedBoardState:
        board = self._load_for_write(case_id, expected_version)
        if not records:
            raise SharedBoardTransitionError("A debate round requires at least one issue")
        next_round = board.current_debate_round + 1
        if next_round > board.max_debate_rounds:
            raise SharedBoardTransitionError("Maximum debate rounds already reached")
        if any(record.round_number != next_round for record in records):
            raise SharedBoardTransitionError(
                f"Every record must use the next debate round ({next_round})"
            )
        updated = board.model_copy(
            update={
                "debate_log": [*board.debate_log, *records],
                "current_debate_round": next_round,
                "status": BoardStatus.DEBATE_IN_PROGRESS,
                "consensus_reached": False,
                "updated_at": utc_now(),
            },
            deep=True,
        )
        return self._save_validated(updated, expected_version)

    def resolve_debate_issue(
        self,
        case_id: UUID,
        *,
        round_number: int,
        issue_code: str,
        target_agent: AgentID,
        specialist_response: str,
        resolution: str,
        expected_version: int,
    ) -> SharedBoardState:
        board = self._load_for_write(case_id, expected_version)
        matched = False
        debate_log: list[DebateRecord] = []
        for record in board.debate_log:
            is_target = (
                record.round_number == round_number
                and record.issue.code == issue_code
                and record.issue.target_agent == target_agent
                and record.status == DebateStatus.OPEN
            )
            if not is_target:
                debate_log.append(record)
                continue
            matched = True
            debate_log.append(
                record.model_copy(
                    update={
                        "status": DebateStatus.RESOLVED,
                        "specialist_response": specialist_response,
                        "resolution": resolution,
                        "resolved_at": utc_now(),
                    }
                )
            )
        if not matched:
            raise SharedBoardTransitionError("Open debate issue was not found")
        updated = board.model_copy(
            update={"debate_log": debate_log, "updated_at": utc_now()},
            deep=True,
        )
        return self._save_validated(updated, expected_version)

    def record_debate_response(
        self,
        case_id: UUID,
        *,
        round_number: int,
        issue_code: str,
        target_agent: AgentID,
        specialist_response: str,
        expected_version: int,
    ) -> SharedBoardState:
        """Record a refinement while leaving resolution to the next Reviewer pass."""

        board = self._load_for_write(case_id, expected_version)
        matched = False
        debate_log: list[DebateRecord] = []
        for record in board.debate_log:
            is_target = (
                record.round_number == round_number
                and record.issue.code == issue_code
                and record.issue.target_agent == target_agent
                and record.status == DebateStatus.OPEN
            )
            if is_target:
                matched = True
                record = record.model_copy(
                    update={"specialist_response": specialist_response}
                )
            debate_log.append(record)
        if not matched:
            raise SharedBoardTransitionError("Open debate issue was not found")
        updated = board.model_copy(
            update={"debate_log": debate_log, "updated_at": utc_now()},
            deep=True,
        )
        return self._save_validated(updated, expected_version)

    def accept_for_manual_review(
        self,
        case_id: UUID,
        issues: Sequence[DebateRecord],
        *,
        expected_version: int,
    ) -> SharedBoardState:
        board = self._load_for_write(case_id, expected_version)
        if board.current_debate_round < board.max_debate_rounds:
            raise SharedBoardTransitionError(
                "Cannot accept issues before the configured debate limit"
            )
        issue_map = {
            (record.issue.code, record.issue.target_agent): record
            for record in issues
        }
        debate_log: list[DebateRecord] = []
        matched: set[tuple[str, AgentID]] = set()
        for record in board.debate_log:
            key = (record.issue.code, record.issue.target_agent)
            if record.status == DebateStatus.OPEN and key in issue_map:
                matched.add(key)
                record = record.model_copy(
                    update={
                        "status": DebateStatus.ACCEPTED_FOR_MANUAL_REVIEW,
                        "resolution": (
                            "Unresolved after the configured debate limit; the human "
                            "officer must review this issue explicitly."
                        ),
                        "resolved_at": utc_now(),
                    }
                )
            debate_log.append(record)
        for key, record in issue_map.items():
            if key not in matched:
                debate_log.append(
                    record.model_copy(
                        update={
                            "status": DebateStatus.ACCEPTED_FOR_MANUAL_REVIEW,
                            "resolution": (
                                "Raised at the debate limit and transferred to human "
                                "review without being treated as resolved."
                            ),
                            "resolved_at": utc_now(),
                        }
                    )
                )
        updated = board.model_copy(
            update={
                "debate_log": debate_log,
                "status": BoardStatus.MAX_ROUNDS_REACHED,
                "consensus_reached": False,
                "updated_at": utc_now(),
            },
            deep=True,
        )
        return self._save_validated(updated, expected_version)

    def mark_consensus(
        self,
        case_id: UUID,
        *,
        expected_version: int,
    ) -> SharedBoardState:
        board = self._load_for_write(case_id, expected_version)
        if any(record.status == DebateStatus.OPEN for record in board.debate_log):
            raise SharedBoardTransitionError(
                "Open debate issues must be resolved before consensus"
            )
        if any(
            assessment.status != AssessmentStatus.SUCCESS
            for assessment in board.specialist_outputs.values()
        ):
            raise SharedBoardTransitionError(
                "All posted specialist assessments must be successful"
            )
        if set(board.specialist_outputs) != SPECIALIST_AGENT_IDS:
            raise SharedBoardTransitionError(
                "All five authorized specialist outputs are required for consensus"
            )
        updated = board.model_copy(
            update={
                "status": BoardStatus.CONSENSUS_REACHED,
                "consensus_reached": True,
                "updated_at": utc_now(),
            },
            deep=True,
        )
        return self._save_validated(updated, expected_version)

    def mark_max_rounds_reached(
        self,
        case_id: UUID,
        *,
        expected_version: int,
    ) -> SharedBoardState:
        board = self._load_for_write(case_id, expected_version)
        if board.current_debate_round < board.max_debate_rounds:
            raise SharedBoardTransitionError(
                "Cannot mark max rounds before the configured limit"
            )
        updated = board.model_copy(
            update={
                "status": BoardStatus.MAX_ROUNDS_REACHED,
                "consensus_reached": False,
                "updated_at": utc_now(),
            },
            deep=True,
        )
        return self._save_validated(updated, expected_version)

    def _load_for_write(
        self,
        case_id: UUID,
        expected_version: int,
    ) -> SharedBoardState:
        board = self.get(case_id)
        if board.version != expected_version:
            raise SharedBoardConflictError(
                f"Expected board version {expected_version}, found {board.version}"
            )
        return board

    def _save_validated(
        self,
        board: SharedBoardState,
        expected_version: int,
    ) -> SharedBoardState:
        validated = SharedBoardState.model_validate(board.model_dump())
        return self._repository.save(validated, expected_version=expected_version)


def _task_status_for_assessment(status: AssessmentStatus) -> TaskStatus:
    return {
        AssessmentStatus.PENDING: TaskStatus.PENDING,
        AssessmentStatus.RUNNING: TaskStatus.RUNNING,
        AssessmentStatus.SUCCESS: TaskStatus.COMPLETED,
        AssessmentStatus.REQUIRES_MORE_DATA: TaskStatus.BLOCKED,
        AssessmentStatus.MANUAL_REVIEW: TaskStatus.BLOCKED,
        AssessmentStatus.ERROR: TaskStatus.ERROR,
    }[status]


__all__ = [
    "InMemorySharedBoardRepository",
    "SharedBoardConflictError",
    "SharedBoardError",
    "SharedBoardManager",
    "SharedBoardNotFoundError",
    "SharedBoardRepository",
    "SharedBoardTransitionError",
]
