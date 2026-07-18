from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.tier1_orchestrator.deep_agent import (
    AssessmentPaused,
    DeepAgentOrchestrator,
)
from app.db.models import (
    AssessmentEvent,
    AssessmentRun,
    AssessmentRunStatus,
    Case,
    CaseStatus,
)
from app.db.session import SessionLocal


ACTIVE_RUN_STATUSES = {
    AssessmentRunStatus.QUEUED.value,
    AssessmentRunStatus.RUNNING.value,
    AssessmentRunStatus.STOP_REQUESTED.value,
}


class AssessmentRunConflict(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def latest_run(db: Session, case_id: UUID) -> AssessmentRun | None:
    return db.scalar(
        select(AssessmentRun)
        .where(AssessmentRun.case_id == case_id)
        .order_by(AssessmentRun.created_at.desc(), AssessmentRun.id.desc())
        .limit(1)
    )


def create_assessment_run(
    db: Session,
    *,
    case: Case,
    started_by: str,
    checkpoint_stage: str = "plan",
) -> AssessmentRun:
    current = latest_run(db, case.id)
    if current is not None and current.status in ACTIVE_RUN_STATUSES:
        raise AssessmentRunConflict("An assessment run is already active")
    run = AssessmentRun(
        case_id=case.id,
        started_by=started_by,
        status=AssessmentRunStatus.QUEUED.value,
        current_stage="queued",
        checkpoint_stage=checkpoint_stage,
    )
    db.add(run)
    db.flush()
    append_event(
        db,
        run=run,
        event_type="RUN_QUEUED",
        stage="queued",
        status="QUEUED",
        title="Đã xếp hàng thẩm định",
        message="Backend đã nhận yêu cầu và sẽ chạy các agent ở tiến trình nền.",
    )
    db.commit()
    return run


def request_stop(db: Session, run: AssessmentRun) -> AssessmentRun:
    if run.status not in ACTIVE_RUN_STATUSES:
        raise AssessmentRunConflict("Only an active assessment can be stopped")
    run.stop_requested = True
    run.status = AssessmentRunStatus.STOP_REQUESTED.value
    run.updated_at = utc_now()
    append_event(
        db,
        run=run,
        event_type="STOP_REQUESTED",
        stage=run.current_stage,
        status="STOP_REQUESTED",
        title="Đã yêu cầu dừng an toàn",
        message=(
            "Agent đang chạy sẽ hoàn tất lượt gọi model hiện tại, sau đó hệ thống "
            "lưu checkpoint và tạm dừng."
        ),
    )
    db.commit()
    return run


def reconcile_orphaned_runs(db: Session) -> int:
    """Recover runs orphaned by a backend process restart.

    execute_assessment_run runs as an in-process background task. If the
    process exits while a run is RUNNING or STOP_REQUESTED, nothing ever
    transitions it to a terminal state: create_assessment_run refuses a new
    run while one is active, and queue_resume only accepts PAUSED/FAILED, so
    the case is stuck with no UI path forward. checkpoint_stage is written
    durably before every pause point, so it is always safe to treat an
    orphaned run as paused there. Call once per process start, before the
    API begins serving, so it can only ever see truly dead runs.
    """

    orphaned = db.scalars(
        select(AssessmentRun).where(
            AssessmentRun.status.in_(
                [
                    AssessmentRunStatus.RUNNING.value,
                    AssessmentRunStatus.STOP_REQUESTED.value,
                ]
            )
        )
    ).all()
    for run in orphaned:
        run.status = AssessmentRunStatus.PAUSED.value
        run.stop_requested = False
        run.updated_at = utc_now()
        append_event(
            db,
            run=run,
            event_type="RUN_PAUSED",
            stage=run.checkpoint_stage,
            status="PAUSED",
            title="Đã khôi phục sau khi khởi động lại",
            message=(
                "Tiến trình trước đó bị gián đoạn khi backend khởi động lại. "
                f"Có thể tiếp tục an toàn từ {run.checkpoint_stage}."
            ),
            evidence={"checkpoint": run.checkpoint_stage},
        )
    db.commit()
    return len(orphaned)


def queue_resume(db: Session, *, case: Case, started_by: str) -> AssessmentRun:
    run = latest_run(db, case.id)
    if run is None:
        if case.status not in {
            CaseStatus.TIER1_PLANNING.value,
            CaseStatus.TIER2_DEBATING.value,
        }:
            raise AssessmentRunConflict("No paused assessment is available")
        checkpoint = (
            "specialists"
            if case.status == CaseStatus.TIER2_DEBATING.value
            else "plan"
        )
        return create_assessment_run(
            db,
            case=case,
            started_by=started_by,
            checkpoint_stage=checkpoint,
        )
    if run.status not in {
        AssessmentRunStatus.PAUSED.value,
        AssessmentRunStatus.FAILED.value,
    }:
        raise AssessmentRunConflict("Only a paused or failed assessment can resume")
    run.status = AssessmentRunStatus.QUEUED.value
    run.current_stage = "queued"
    run.stop_requested = False
    run.started_by = started_by
    run.error_message = None
    run.completed_at = None
    run.updated_at = utc_now()
    append_event(
        db,
        run=run,
        event_type="RUN_RESUMED",
        stage=run.checkpoint_stage,
        status="QUEUED",
        title="Tiếp tục từ checkpoint",
        message=f"Sẽ tiếp tục tại công đoạn {run.checkpoint_stage}.",
        evidence={"checkpoint": run.checkpoint_stage},
    )
    db.commit()
    return run


def append_event(
    db: Session,
    *,
    run: AssessmentRun,
    event_type: str,
    stage: str,
    status: str,
    title: str,
    message: str,
    agent_id: str | None = None,
    evidence: dict[str, object] | None = None,
) -> AssessmentEvent:
    event = AssessmentEvent(
        run_id=run.id,
        case_id=run.case_id,
        event_type=event_type,
        stage=stage,
        agent_id=agent_id,
        status=status,
        title=title,
        message=message,
        evidence=evidence or {},
    )
    db.add(event)
    db.flush()
    return event


def execute_assessment_run(run_id: UUID) -> None:
    """FastAPI background task entrypoint. Exceptions are persisted, never leaked."""

    db = SessionLocal()
    try:
        run = db.get(AssessmentRun, run_id)
        if run is None:
            return
        run.status = AssessmentRunStatus.RUNNING.value
        run.current_stage = run.checkpoint_stage
        run.started_at = run.started_at or utc_now()
        run.updated_at = utc_now()
        append_event(
            db,
            run=run,
            event_type="RUN_STARTED",
            stage=run.current_stage,
            status="RUNNING",
            title="Các agent bắt đầu làm việc",
            message="Luồng thẩm định đang chạy và sẽ phát sự kiện theo thời gian thực.",
        )
        db.commit()

        def event_callback(
            stage: str,
            agent_id: str | None,
            event_status: str,
            title: str,
            message: str,
            evidence: dict[str, object],
        ) -> None:
            active = db.get(AssessmentRun, run_id)
            if active is None:
                return
            active.current_stage = stage
            active.updated_at = utc_now()
            append_event(
                db,
                run=active,
                event_type="AGENT_ACTIVITY" if agent_id else "STAGE_ACTIVITY",
                stage=stage,
                agent_id=agent_id,
                status=event_status,
                title=title,
                message=message,
                evidence=evidence,
            )
            db.commit()

        def checkpoint_callback(next_stage: str) -> None:
            active = db.get(AssessmentRun, run_id)
            if active is None:
                return
            active.checkpoint_stage = next_stage
            active.updated_at = utc_now()
            db.commit()

        def stop_checker() -> bool:
            db.expire_all()
            active = db.get(AssessmentRun, run_id)
            return bool(active and active.stop_requested)

        DeepAgentOrchestrator(
            db,
            event_callback=event_callback,
            checkpoint_callback=checkpoint_callback,
            stop_checker=stop_checker,
        ).run(run.case_id, resume_from=run.checkpoint_stage)

        active = db.get(AssessmentRun, run_id)
        if active is not None:
            active.status = AssessmentRunStatus.COMPLETED.value
            active.current_stage = "completed"
            active.checkpoint_stage = "completed"
            active.completed_at = utc_now()
            active.updated_at = utc_now()
            append_event(
                db,
                run=active,
                event_type="RUN_COMPLETED",
                stage="completed",
                status="COMPLETED",
                title="Hoàn tất thẩm định AI",
                message="Kết quả đã chuyển tới cổng xác minh của chuyên viên.",
            )
            db.commit()
    except AssessmentPaused:
        db.rollback()
        active = db.get(AssessmentRun, run_id)
        if active is not None:
            active.status = AssessmentRunStatus.PAUSED.value
            active.stop_requested = False
            active.completed_at = utc_now()
            active.updated_at = utc_now()
            append_event(
                db,
                run=active,
                event_type="RUN_PAUSED",
                stage=active.checkpoint_stage,
                status="PAUSED",
                title="Đã tạm dừng tại checkpoint",
                message=f"Có thể tiếp tục an toàn từ {active.checkpoint_stage}.",
                evidence={"checkpoint": active.checkpoint_stage},
            )
            db.commit()
    except Exception as exc:
        db.rollback()
        active = db.get(AssessmentRun, run_id)
        if active is not None:
            active.status = AssessmentRunStatus.FAILED.value
            active.error_message = f"{type(exc).__name__}: {exc}"[:2_000]
            active.completed_at = utc_now()
            active.updated_at = utc_now()
            append_event(
                db,
                run=active,
                event_type="RUN_FAILED",
                stage=active.current_stage,
                status="FAILED",
                title="Luồng thẩm định gặp lỗi",
                message=(
                    "Checkpoint đã được giữ lại. Có thể bấm Tiếp tục để thử lại "
                    "agent/công đoạn chưa hoàn thành."
                ),
                evidence={"error_type": type(exc).__name__},
            )
            db.commit()
    finally:
        db.close()
