from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    BloodPressureReading,
    ClinicianProfile,
    ContactAttempt,
    PatientMessage,
    ReviewTask,
    RuleEvaluation,
    TaskEvidence,
    TaskStatus,
    User,
    UserRole,
)
from app.schemas import (
    ClinicianAuditEventDetail,
    ClinicianContactAttemptDetail,
    ClinicianOwnerSummary,
    ClinicianPatientMessageDetail,
    ClinicianTaskAllowedActions,
    ClinicianTaskDetailResponse,
    ClinicianTaskEvidenceDetail,
    ClinicianTaskReadingDetail,
)
from app.services.clinician_dashboard import (
    build_task_queue_item,
    list_clinician_owners,
)
from app.services.tasks import TaskTransitionError, transition_task


class ClinicianTaskError(ValueError):
    """Raised when a clinician task action cannot be completed safely."""


class ClinicianTaskNotFoundError(ClinicianTaskError):
    """Raised when a requested clinician task does not exist."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _task(db: Session, task_id: str, *, lock: bool = False) -> ReviewTask:
    statement = select(ReviewTask).where(ReviewTask.id == task_id)
    if lock:
        statement = statement.with_for_update()
    task = db.scalar(statement)
    if task is None:
        raise ClinicianTaskNotFoundError("Clinician task not found")
    return task


def _owner(db: Session, clinician_id: str) -> ClinicianOwnerSummary:
    profile = db.get(ClinicianProfile, clinician_id)
    if profile is None:
        raise ClinicianTaskError("Assigned clinician does not exist")
    user = db.get(User, profile.user_id)
    if user is None or user.role is not UserRole.CLINICIAN or not user.active:
        raise ClinicianTaskError("Assigned clinician is not an active clinician")
    return ClinicianOwnerSummary(
        clinician_id=profile.id,
        display_name=user.display_name,
        display_role=profile.display_role,
    )


def _require_owner(task: ReviewTask, clinician: ClinicianProfile) -> None:
    if task.assigned_clinician_id != clinician.id:
        raise ClinicianTaskError("Task action requires the assigned clinician")


def _audit(
    db: Session,
    *,
    task: ReviewTask,
    clinician: ClinicianProfile,
    event_type: str,
    metadata: dict[str, object],
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=clinician.user_id,
            patient_id=task.patient_id,
            entity_type="review_task",
            entity_id=task.id,
            event_type=event_type,
            event_metadata=metadata,
        )
    )


def _title(evaluation: RuleEvaluation) -> str:
    value = evaluation.evidence.get("title")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "Configured review marker"


def _observed_values(evaluation: RuleEvaluation) -> list[dict[str, object]]:
    value = evaluation.evidence.get("observed_values", [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _allowed_actions(
    task: ReviewTask,
    clinician: ClinicianProfile,
) -> ClinicianTaskAllowedActions:
    owns_task = task.assigned_clinician_id == clinician.id
    can_communicate = task.status is TaskStatus.IN_REVIEW and owns_task
    return ClinicianTaskAllowedActions(
        can_assign=task.status in {TaskStatus.OPEN, TaskStatus.ASSIGNED, TaskStatus.IN_REVIEW},
        can_unassign=task.status is TaskStatus.ASSIGNED,
        can_acknowledge=(
            task.status is TaskStatus.ASSIGNED and owns_task and task.acknowledged_at is None
        ),
        can_start_review=(
            task.status is TaskStatus.ASSIGNED and owns_task and task.acknowledged_at is not None
        ),
        can_return_to_assigned=task.status is TaskStatus.IN_REVIEW and owns_task,
        can_resolve=task.status is TaskStatus.IN_REVIEW and owns_task,
        can_reopen=task.status is TaskStatus.RESOLVED and owns_task,
        can_record_contact=can_communicate,
        can_draft_message=can_communicate,
    )


def build_task_detail(
    db: Session,
    *,
    task_id: str,
    clinician: ClinicianProfile,
    now: datetime,
) -> ClinicianTaskDetailResponse:
    task = _task(db, task_id)
    readings = list(
        db.scalars(
            select(BloodPressureReading)
            .where(BloodPressureReading.patient_id == task.patient_id)
            .order_by(
                BloodPressureReading.measured_at.desc(),
                BloodPressureReading.id.desc(),
            )
        )
    )
    evaluations = list(
        db.scalars(
            select(RuleEvaluation)
            .join(TaskEvidence, TaskEvidence.rule_evaluation_id == RuleEvaluation.id)
            .where(TaskEvidence.task_id == task.id)
            .order_by(RuleEvaluation.evaluated_at.desc(), RuleEvaluation.id.desc())
        )
    )
    contact_attempts = list(
        db.scalars(
            select(ContactAttempt)
            .where(ContactAttempt.task_id == task.id)
            .order_by(ContactAttempt.attempted_at.desc(), ContactAttempt.id.desc())
        )
    )
    messages = list(
        db.scalars(
            select(PatientMessage)
            .where(PatientMessage.task_id == task.id)
            .order_by(PatientMessage.created_at.desc(), PatientMessage.id.desc())
        )
    )
    audit_events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "review_task", AuditEvent.entity_id == task.id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        )
    )
    current_time = _utc(now)
    return ClinicianTaskDetailResponse(
        generated_at=current_time,
        task=build_task_queue_item(db, task, now=current_time),
        acknowledged_at=_utc(task.acknowledged_at) if task.acknowledged_at else None,
        resolved_at=_utc(task.resolved_at) if task.resolved_at else None,
        outcome_code=task.outcome_code,
        outcome_note=task.outcome_note,
        reopened_count=task.reopened_count,
        readings=[
            ClinicianTaskReadingDetail(
                reading_id=reading.id,
                systolic=reading.systolic,
                diastolic=reading.diastolic,
                measured_at=_utc(reading.measured_at),
                confirmed_at=_utc(reading.confirmed_at),
                medication_taken=reading.medication_taken,
                missed_medication_reason_code=reading.missed_medication_reason_code,
                context_codes=reading.context_codes,
                note=reading.note,
            )
            for reading in readings
        ],
        evidence=[
            ClinicianTaskEvidenceDetail(
                rule_evaluation_id=evaluation.id,
                reading_id=evaluation.reading_id,
                rule_id=evaluation.rule_id,
                rule_version=evaluation.rule_version,
                priority=evaluation.priority,
                title=_title(evaluation),
                reason=evaluation.reason,
                source_reference=evaluation.source_reference,
                evaluated_at=_utc(evaluation.evaluated_at),
                observed_values=_observed_values(evaluation),
            )
            for evaluation in evaluations
        ],
        available_owners=list_clinician_owners(db),
        current_clinician=_owner(db, clinician.id),
        allowed_actions=_allowed_actions(task, clinician),
        contact_attempts=[
            ClinicianContactAttemptDetail(
                contact_attempt_id=attempt.id,
                clinician=_owner(db, attempt.clinician_id),
                channel=attempt.channel,
                outcome_code=attempt.outcome_code,
                note=attempt.note,
                attempted_at=_utc(attempt.attempted_at),
            )
            for attempt in contact_attempts
        ],
        messages=[
            ClinicianPatientMessageDetail(
                message_id=message.id,
                channel=message.channel,
                language=message.language,
                content=message.content,
                generation_type=message.generation_type,
                approval_status=message.approval_status,
                approved_by=message.approved_by,
                approved_at=_utc(message.approved_at) if message.approved_at else None,
                sent_at=_utc(message.sent_at) if message.sent_at else None,
                delivery_status=message.delivery_status,
                created_at=_utc(message.created_at),
            )
            for message in messages
        ],
        audit_events=[
            ClinicianAuditEventDetail(
                audit_event_id=event.id,
                actor_display_name=(
                    actor.display_name
                    if event.actor_user_id and (actor := db.get(User, event.actor_user_id))
                    else "System"
                ),
                event_type=event.event_type,
                metadata=event.event_metadata,
                created_at=_utc(event.created_at),
            )
            for event in audit_events
        ],
    )


def assign_task(
    db: Session,
    *,
    task_id: str,
    actor: ClinicianProfile,
    clinician_id: str | None,
    at: datetime,
) -> None:
    task = _task(db, task_id, lock=True)
    previous_owner = task.assigned_clinician_id

    if clinician_id is None:
        if task.status is not TaskStatus.ASSIGNED:
            raise ClinicianTaskError("Only an assigned task can be explicitly unassigned")
        transition_task(task, TaskStatus.OPEN, at=at)
        task.acknowledged_at = None
        _audit(
            db,
            task=task,
            clinician=actor,
            event_type="review_task.unassigned",
            metadata={"previous_clinician_id": previous_owner},
        )
        db.commit()
        return

    _owner(db, clinician_id)
    if task.status is TaskStatus.RESOLVED:
        raise ClinicianTaskError("A resolved task must be reopened before assignment changes")
    if task.status is TaskStatus.OPEN:
        transition_task(
            task,
            TaskStatus.ASSIGNED,
            at=at,
            assigned_clinician_id=clinician_id,
        )
        event_type = "review_task.assigned"
    elif task.status is TaskStatus.IN_REVIEW:
        transition_task(task, TaskStatus.ASSIGNED, at=at)
        task.assigned_clinician_id = clinician_id
        event_type = "review_task.returned_to_assigned"
    else:
        if previous_owner == clinician_id:
            return
        task.assigned_clinician_id = clinician_id
        event_type = "review_task.reassigned"

    task.acknowledged_at = None
    _audit(
        db,
        task=task,
        clinician=actor,
        event_type=event_type,
        metadata={
            "previous_clinician_id": previous_owner,
            "current_clinician_id": clinician_id,
        },
    )
    db.commit()


def acknowledge_task(
    db: Session,
    *,
    task_id: str,
    actor: ClinicianProfile,
    at: datetime,
) -> None:
    task = _task(db, task_id, lock=True)
    if task.status is not TaskStatus.ASSIGNED:
        raise ClinicianTaskError("Only an assigned task can be acknowledged")
    _require_owner(task, actor)
    if task.acknowledged_at is not None:
        return
    task.acknowledged_at = at
    _audit(
        db,
        task=task,
        clinician=actor,
        event_type="review_task.acknowledged",
        metadata={"acknowledged_at": _utc(at).isoformat()},
    )
    db.commit()


def start_task_review(
    db: Session,
    *,
    task_id: str,
    actor: ClinicianProfile,
    at: datetime,
) -> None:
    task = _task(db, task_id, lock=True)
    _require_owner(task, actor)
    if task.status is not TaskStatus.ASSIGNED:
        raise ClinicianTaskError("Only an assigned task can enter review")
    if task.acknowledged_at is None:
        raise ClinicianTaskError("Task must be acknowledged before review starts")
    transition_task(task, TaskStatus.IN_REVIEW, at=at)
    _audit(
        db,
        task=task,
        clinician=actor,
        event_type="review_task.review_started",
        metadata={},
    )
    db.commit()


def resolve_task(
    db: Session,
    *,
    task_id: str,
    actor: ClinicianProfile,
    outcome_code: str,
    outcome_note: str | None,
    at: datetime,
) -> None:
    task = _task(db, task_id, lock=True)
    _require_owner(task, actor)
    try:
        transition_task(
            task,
            TaskStatus.RESOLVED,
            at=at,
            outcome_code=outcome_code,
            outcome_note=outcome_note,
        )
    except TaskTransitionError as error:
        raise ClinicianTaskError(str(error)) from error
    _audit(
        db,
        task=task,
        clinician=actor,
        event_type="review_task.resolved",
        metadata={
            "outcome_code": outcome_code,
            "outcome_note_recorded": outcome_note is not None,
        },
    )
    db.commit()


def reopen_task(
    db: Session,
    *,
    task_id: str,
    actor: ClinicianProfile,
    reason: str,
    at: datetime,
) -> None:
    task = _task(db, task_id, lock=True)
    _require_owner(task, actor)
    try:
        transition_task(
            task,
            TaskStatus.IN_REVIEW,
            at=at,
            reopen_reason=reason,
        )
    except TaskTransitionError as error:
        raise ClinicianTaskError(str(error)) from error
    _audit(
        db,
        task=task,
        clinician=actor,
        event_type="review_task.reopened",
        metadata={"reason": reason},
    )
    db.commit()
