from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    BloodPressureReading,
    ReviewTask,
    RuleEvaluation,
    TaskEvidence,
    TaskPriority,
    TaskStatus,
)
from app.seed import PATIENT_IDS, USER_IDS, seed_demo_data
from app.services.tasks import TaskTransitionError, sync_review_tasks, transition_task

NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


def _evaluation(
    *,
    key: int,
    reading: BloodPressureReading,
    priority: TaskPriority,
    evaluated_at: datetime,
    version: str = "task-test-1",
    sla_minutes: int = 240,
) -> RuleEvaluation:
    return RuleEvaluation(
        id=f"85000000-0000-4000-8000-{key:012d}",
        patient_id=reading.patient_id,
        reading_id=reading.id,
        rule_id="test.same-material-rule",
        rule_version=version,
        triggered=True,
        priority=priority,
        reason="Synthetic task deduplication test evidence.",
        evidence={"sla_minutes": sla_minutes, "synthetic": True},
        source_reference="Test-only synthetic configuration",
        evaluated_at=evaluated_at,
    )


def _task(status: TaskStatus = TaskStatus.OPEN) -> ReviewTask:
    return ReviewTask(
        id="86000000-0000-4000-8000-000000000001",
        patient_id=PATIENT_IDS["rudo"],
        priority=TaskPriority.NEEDS_REVIEW,
        status=status,
        primary_rule_evaluation_id="85000000-0000-4000-8000-000000000001",
        opened_at=NOW,
        due_at=NOW + timedelta(hours=4),
    )


def test_same_open_rule_task_reuses_task_adds_evidence_and_elevates_priority(
    db_session: Session,
) -> None:
    seed_demo_data(db_session, now=NOW)
    db_session.commit()
    readings = db_session.scalars(
        select(BloodPressureReading)
        .where(BloodPressureReading.patient_id == PATIENT_IDS["rudo"])
        .order_by(BloodPressureReading.measured_at.asc())
    ).all()
    first = _evaluation(
        key=1,
        reading=readings[0],
        priority=TaskPriority.WATCH,
        evaluated_at=NOW - timedelta(hours=1),
        sla_minutes=720,
    )
    second = _evaluation(
        key=2,
        reading=readings[1],
        priority=TaskPriority.URGENT_REVIEW,
        evaluated_at=NOW,
        sla_minutes=30,
    )
    db_session.add_all([first, second])
    db_session.flush()

    first_sync = sync_review_tasks(
        db_session,
        evaluations=[first],
        actor_user_id=USER_IDS["rudo"],
    )
    first_task = first_sync.tasks[0]
    original_due_at = first_task.due_at
    second_sync = sync_review_tasks(
        db_session,
        evaluations=[second],
        actor_user_id=USER_IDS["rudo"],
    )
    db_session.commit()

    assert first_sync.created_task_ids == [first_task.id]
    assert second_sync.created_task_ids == []
    assert second_sync.updated_task_ids == [first_task.id]
    assert second_sync.tasks[0].id == first_task.id
    assert first_task.priority is TaskPriority.URGENT_REVIEW
    assert first_task.due_at is not None and original_due_at is not None
    assert first_task.due_at < original_due_at
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(TaskEvidence)
            .where(TaskEvidence.task_id == first_task.id)
        )
        == 2
    )
    event_types = set(
        db_session.scalars(
            select(AuditEvent.event_type).where(AuditEvent.entity_id == first_task.id)
        ).all()
    )
    assert event_types == {
        "review_task.created",
        "review_task.evidence_added",
        "review_task.priority_elevated",
    }


def test_resolved_task_does_not_absorb_new_evidence(db_session: Session) -> None:
    seed_demo_data(db_session, now=NOW)
    db_session.commit()
    readings = db_session.scalars(
        select(BloodPressureReading)
        .where(BloodPressureReading.patient_id == PATIENT_IDS["rudo"])
        .order_by(BloodPressureReading.measured_at.asc())
    ).all()
    first = _evaluation(
        key=1,
        reading=readings[0],
        priority=TaskPriority.WATCH,
        evaluated_at=NOW - timedelta(hours=1),
    )
    second = _evaluation(
        key=2,
        reading=readings[1],
        priority=TaskPriority.WATCH,
        evaluated_at=NOW,
    )
    db_session.add_all([first, second])
    db_session.flush()
    first_task = sync_review_tasks(
        db_session,
        evaluations=[first],
        actor_user_id=None,
    ).tasks[0]
    first_task.status = TaskStatus.RESOLVED
    first_task.resolved_at = NOW
    db_session.flush()

    second_task = sync_review_tasks(
        db_session,
        evaluations=[second],
        actor_user_id=None,
    ).tasks[0]

    assert second_task.id != first_task.id


def test_task_state_machine_supports_only_locked_transitions() -> None:
    task = _task()

    assigned = transition_task(
        task,
        TaskStatus.ASSIGNED,
        at=NOW,
        assigned_clinician_id="21000000-0000-4000-8000-000000000001",
    )
    assert assigned.previous_status is TaskStatus.OPEN
    assert task.status is TaskStatus.ASSIGNED

    transition_task(task, TaskStatus.IN_REVIEW, at=NOW + timedelta(minutes=5))
    resolved = transition_task(
        task,
        TaskStatus.RESOLVED,
        at=NOW + timedelta(minutes=10),
        outcome_code="follow_up_completed",
        outcome_note="Synthetic workflow outcome.",
    )
    assert resolved.current_status is TaskStatus.RESOLVED
    assert task.resolved_at == NOW + timedelta(minutes=10)

    with pytest.raises(TaskTransitionError, match="Reopen requires a reason"):
        transition_task(task, TaskStatus.IN_REVIEW, at=NOW + timedelta(minutes=15))

    reopened = transition_task(
        task,
        TaskStatus.IN_REVIEW,
        at=NOW + timedelta(minutes=15),
        reopen_reason="New synthetic evidence requires another review.",
    )
    assert reopened.reason == "New synthetic evidence requires another review."
    assert task.reopened_count == 1
    assert task.resolved_at is None
    assert task.outcome_code is None

    transition_task(task, TaskStatus.ASSIGNED, at=NOW + timedelta(minutes=20))
    transition_task(task, TaskStatus.OPEN, at=NOW + timedelta(minutes=25))
    assert task.status is TaskStatus.OPEN
    assert task.assigned_clinician_id is None


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (TaskStatus.OPEN, TaskStatus.IN_REVIEW),
        (TaskStatus.OPEN, TaskStatus.RESOLVED),
        (TaskStatus.ASSIGNED, TaskStatus.RESOLVED),
        (TaskStatus.RESOLVED, TaskStatus.OPEN),
        (TaskStatus.RESOLVED, TaskStatus.ASSIGNED),
    ],
)
def test_task_state_machine_rejects_invalid_transitions(
    start: TaskStatus,
    target: TaskStatus,
) -> None:
    task = _task(start)
    if start is not TaskStatus.OPEN:
        task.assigned_clinician_id = "21000000-0000-4000-8000-000000000001"

    with pytest.raises(TaskTransitionError, match="is not permitted"):
        transition_task(task, target, at=NOW)

    assert task.status is start


def test_task_state_machine_requires_assignment_and_resolution_outcome() -> None:
    task = _task()
    with pytest.raises(TaskTransitionError, match="requires a clinician"):
        transition_task(task, TaskStatus.ASSIGNED, at=NOW)

    task.status = TaskStatus.IN_REVIEW
    task.assigned_clinician_id = "21000000-0000-4000-8000-000000000001"
    with pytest.raises(TaskTransitionError, match="requires an outcome code"):
        transition_task(task, TaskStatus.RESOLVED, at=NOW)
