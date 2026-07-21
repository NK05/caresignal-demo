from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    ReviewTask,
    RuleEvaluation,
    TaskEvidence,
    TaskPriority,
    TaskStatus,
)

ACTIVE_TASK_STATUSES = (TaskStatus.OPEN, TaskStatus.ASSIGNED, TaskStatus.IN_REVIEW)
PRIORITY_RANK = {
    TaskPriority.ROUTINE: 0,
    TaskPriority.WATCH: 1,
    TaskPriority.NEEDS_REVIEW: 2,
    TaskPriority.URGENT_REVIEW: 3,
}
ALLOWED_TASK_TRANSITIONS = {
    TaskStatus.OPEN: frozenset({TaskStatus.ASSIGNED}),
    TaskStatus.ASSIGNED: frozenset({TaskStatus.OPEN, TaskStatus.IN_REVIEW}),
    TaskStatus.IN_REVIEW: frozenset({TaskStatus.ASSIGNED, TaskStatus.RESOLVED}),
    TaskStatus.RESOLVED: frozenset({TaskStatus.IN_REVIEW}),
}


@dataclass(frozen=True)
class TaskSyncResult:
    tasks: list[ReviewTask]
    created_task_ids: list[str]
    updated_task_ids: list[str]

    @property
    def care_team_notified(self) -> bool:
        return bool(self.tasks)


@dataclass(frozen=True)
class TaskTransition:
    previous_status: TaskStatus
    current_status: TaskStatus
    reason: str | None = None


class TaskTransitionError(ValueError):
    """Raised when a review-task state change violates the locked workflow."""


def _sla_minutes(evaluation: RuleEvaluation) -> int:
    value = evaluation.evidence.get("sla_minutes", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _due_at(evaluation: RuleEvaluation) -> datetime:
    return evaluation.evaluated_at + timedelta(minutes=_sla_minutes(evaluation))


def _find_covering_task(
    db: Session,
    *,
    evaluation: RuleEvaluation,
) -> ReviewTask | None:
    return db.scalar(
        select(ReviewTask)
        .join(TaskEvidence, TaskEvidence.task_id == ReviewTask.id)
        .join(
            RuleEvaluation,
            RuleEvaluation.id == TaskEvidence.rule_evaluation_id,
        )
        .where(
            ReviewTask.patient_id == evaluation.patient_id,
            ReviewTask.status.in_(ACTIVE_TASK_STATUSES),
            RuleEvaluation.rule_id == evaluation.rule_id,
            RuleEvaluation.rule_version == evaluation.rule_version,
        )
        .order_by(ReviewTask.opened_at.asc(), ReviewTask.id.asc())
        .with_for_update()
    )


def _add_task_audit(
    db: Session,
    *,
    task: ReviewTask,
    actor_user_id: str | None,
    event_type: str,
    metadata: dict[str, object],
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            patient_id=task.patient_id,
            entity_type="review_task",
            entity_id=task.id,
            event_type=event_type,
            event_metadata=metadata,
        )
    )


def sync_review_tasks(
    db: Session,
    *,
    evaluations: list[RuleEvaluation],
    actor_user_id: str | None,
) -> TaskSyncResult:
    tasks_by_id: dict[str, ReviewTask] = {}
    created_task_ids: list[str] = []
    updated_task_ids: list[str] = []

    triggered = sorted(
        (evaluation for evaluation in evaluations if evaluation.triggered),
        key=lambda evaluation: (
            evaluation.rule_id,
            evaluation.rule_version,
            evaluation.id,
        ),
    )
    for evaluation in triggered:
        task = _find_covering_task(db, evaluation=evaluation)
        if task is None:
            task = ReviewTask(
                patient_id=evaluation.patient_id,
                priority=evaluation.priority,
                status=TaskStatus.OPEN,
                primary_rule_evaluation_id=evaluation.id,
                opened_at=evaluation.evaluated_at,
                due_at=_due_at(evaluation),
            )
            db.add(task)
            db.flush()
            db.add(TaskEvidence(task_id=task.id, rule_evaluation_id=evaluation.id))
            _add_task_audit(
                db,
                task=task,
                actor_user_id=actor_user_id,
                event_type="review_task.created",
                metadata={
                    "rule_evaluation_id": evaluation.id,
                    "rule_id": evaluation.rule_id,
                    "rule_version": evaluation.rule_version,
                    "priority": evaluation.priority.value,
                },
            )
            created_task_ids.append(task.id)
        else:
            evidence_link = db.get(TaskEvidence, (task.id, evaluation.id))
            if evidence_link is None:
                db.add(TaskEvidence(task_id=task.id, rule_evaluation_id=evaluation.id))
                _add_task_audit(
                    db,
                    task=task,
                    actor_user_id=actor_user_id,
                    event_type="review_task.evidence_added",
                    metadata={
                        "rule_evaluation_id": evaluation.id,
                        "rule_id": evaluation.rule_id,
                        "rule_version": evaluation.rule_version,
                    },
                )
            if PRIORITY_RANK[evaluation.priority] > PRIORITY_RANK[task.priority]:
                previous_priority = task.priority
                task.priority = evaluation.priority
                task.due_at = min(
                    due_at for due_at in (task.due_at, _due_at(evaluation)) if due_at is not None
                )
                _add_task_audit(
                    db,
                    task=task,
                    actor_user_id=actor_user_id,
                    event_type="review_task.priority_elevated",
                    metadata={
                        "previous_priority": previous_priority.value,
                        "current_priority": evaluation.priority.value,
                        "rule_evaluation_id": evaluation.id,
                    },
                )
            updated_task_ids.append(task.id)

        tasks_by_id[task.id] = task

    db.flush()
    return TaskSyncResult(
        tasks=list(tasks_by_id.values()),
        created_task_ids=list(dict.fromkeys(created_task_ids)),
        updated_task_ids=list(dict.fromkeys(updated_task_ids)),
    )


def transition_task(
    task: ReviewTask,
    target: TaskStatus,
    *,
    at: datetime,
    assigned_clinician_id: str | None = None,
    outcome_code: str | None = None,
    outcome_note: str | None = None,
    reopen_reason: str | None = None,
) -> TaskTransition:
    previous = task.status
    if target not in ALLOWED_TASK_TRANSITIONS[previous]:
        raise TaskTransitionError(
            f"Transition from {previous.value} to {target.value} is not permitted"
        )

    if previous is TaskStatus.OPEN and target is TaskStatus.ASSIGNED:
        if not assigned_clinician_id:
            raise TaskTransitionError("Assignment requires a clinician")
        task.assigned_clinician_id = assigned_clinician_id
    elif previous is TaskStatus.ASSIGNED and target is TaskStatus.OPEN:
        task.assigned_clinician_id = None
    elif target is TaskStatus.IN_REVIEW and previous is not TaskStatus.RESOLVED:
        if not task.assigned_clinician_id:
            raise TaskTransitionError("Review requires an assigned clinician")
    elif previous is TaskStatus.IN_REVIEW and target is TaskStatus.RESOLVED:
        if not outcome_code or not outcome_code.strip():
            raise TaskTransitionError("Resolution requires an outcome code")
        task.outcome_code = outcome_code.strip()
        task.outcome_note = outcome_note.strip() if outcome_note else None
        task.resolved_at = at
    elif previous is TaskStatus.RESOLVED and target is TaskStatus.IN_REVIEW:
        if not reopen_reason or not reopen_reason.strip():
            raise TaskTransitionError("Reopen requires a reason")
        if not task.assigned_clinician_id:
            raise TaskTransitionError("Reopened review requires an assigned clinician")
        task.reopened_count = (task.reopened_count or 0) + 1
        task.resolved_at = None
        task.outcome_code = None
        task.outcome_note = None

    task.status = target
    return TaskTransition(
        previous_status=previous,
        current_status=target,
        reason=reopen_reason.strip() if reopen_reason else None,
    )
