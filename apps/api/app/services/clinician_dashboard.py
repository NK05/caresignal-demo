from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BloodPressureReading,
    ClinicianProfile,
    Language,
    MedicationStatus,
    PatientProfile,
    ReviewTask,
    RuleEvaluation,
    TaskEvidence,
    TaskPriority,
    TaskStatus,
    User,
)
from app.schemas import (
    ClinicianDashboardResponse,
    ClinicianDashboardSummary,
    ClinicianOwnerSummary,
    ClinicianTaskListResponse,
    ClinicianTaskQueueItem,
    DashboardReadingSummary,
)
from app.services.tasks import ACTIVE_TASK_STATUSES, PRIORITY_RANK


@dataclass(frozen=True)
class TaskQueueFilters:
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    owner: str | None = None
    overdue: bool | None = None
    language: Language | None = None
    medication_adherence_signal: bool | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _owner_summary(db: Session, clinician_id: str | None) -> ClinicianOwnerSummary | None:
    if clinician_id is None:
        return None
    profile = db.get(ClinicianProfile, clinician_id)
    if profile is None:
        return None
    user = db.get(User, profile.user_id)
    if user is None:
        return None
    return ClinicianOwnerSummary(
        clinician_id=profile.id,
        display_name=user.display_name,
        display_role=profile.display_role,
    )


def list_clinician_owners(db: Session) -> list[ClinicianOwnerSummary]:
    profiles = list(db.scalars(select(ClinicianProfile).order_by(ClinicianProfile.id.asc())))
    return [owner for profile in profiles if (owner := _owner_summary(db, profile.id)) is not None]


def build_task_queue_item(
    db: Session,
    task: ReviewTask,
    *,
    now: datetime,
) -> ClinicianTaskQueueItem:
    patient = db.get(PatientProfile, task.patient_id)
    if patient is None:
        raise RuntimeError(f"Task {task.id} references a missing patient")
    patient_user = db.get(User, patient.user_id)
    if patient_user is None:
        raise RuntimeError(f"Patient {patient.id} references a missing user")
    primary_evaluation = db.get(RuleEvaluation, task.primary_rule_evaluation_id)
    if primary_evaluation is None:
        raise RuntimeError(f"Task {task.id} references a missing primary evaluation")
    latest_reading = db.scalar(
        select(BloodPressureReading)
        .where(BloodPressureReading.patient_id == patient.id)
        .order_by(BloodPressureReading.measured_at.desc(), BloodPressureReading.id.desc())
    )
    if latest_reading is None:
        raise RuntimeError(f"Task {task.id} has no confirmed patient reading")

    evidence_readings = list(
        db.scalars(
            select(BloodPressureReading)
            .join(RuleEvaluation, RuleEvaluation.reading_id == BloodPressureReading.id)
            .join(TaskEvidence, TaskEvidence.rule_evaluation_id == RuleEvaluation.id)
            .where(TaskEvidence.task_id == task.id)
        )
    )
    evidence_count = len(
        list(db.scalars(select(TaskEvidence).where(TaskEvidence.task_id == task.id)))
    )
    current_time = _utc(now)
    opened_at = _utc(task.opened_at)
    due_at = _utc(task.due_at) if task.due_at is not None else None
    active = task.status in ACTIVE_TASK_STATUSES
    flag_title = primary_evaluation.evidence.get("title")
    if not isinstance(flag_title, str) or not flag_title.strip():
        flag_title = "Configured review marker"

    return ClinicianTaskQueueItem(
        task_id=task.id,
        patient_id=patient.id,
        patient_synthetic_identifier=patient.synthetic_identifier,
        patient_display_name=patient_user.display_name,
        preferred_language=patient_user.preferred_language,
        preferred_channel=patient.preferred_channel,
        priority=task.priority,
        status=task.status,
        flag_title=flag_title,
        flag_reason=primary_evaluation.reason,
        rule_version=primary_evaluation.rule_version,
        latest_reading=DashboardReadingSummary(
            reading_id=latest_reading.id,
            systolic=latest_reading.systolic,
            diastolic=latest_reading.diastolic,
            measured_at=_utc(latest_reading.measured_at),
            medication_taken=latest_reading.medication_taken,
        ),
        medication_adherence_signal=any(
            reading.medication_taken is MedicationStatus.NO for reading in evidence_readings
        ),
        assigned_owner=_owner_summary(db, task.assigned_clinician_id),
        evidence_count=evidence_count,
        opened_at=opened_at,
        due_at=due_at,
        task_age_minutes=max(0, int((current_time - opened_at).total_seconds() // 60)),
        overdue=bool(active and due_at is not None and due_at < current_time),
        unacknowledged=bool(task.status is TaskStatus.ASSIGNED and task.acknowledged_at is None),
    )


def _matches_filters(item: ClinicianTaskQueueItem, filters: TaskQueueFilters) -> bool:
    if filters.priority is not None and item.priority is not filters.priority:
        return False
    if filters.status is not None and item.status is not filters.status:
        return False
    if filters.status is None and item.status not in ACTIVE_TASK_STATUSES:
        return False
    if filters.owner == "unassigned" and item.assigned_owner is not None:
        return False
    if filters.owner not in (None, "unassigned") and (
        item.assigned_owner is None or item.assigned_owner.clinician_id != filters.owner
    ):
        return False
    if filters.overdue is not None and item.overdue is not filters.overdue:
        return False
    if filters.language is not None and item.preferred_language is not filters.language:
        return False
    if (
        filters.medication_adherence_signal is not None
        and item.medication_adherence_signal is not filters.medication_adherence_signal
    ):
        return False
    return True


def build_task_queue(
    db: Session,
    *,
    now: datetime,
    filters: TaskQueueFilters | None = None,
) -> list[ClinicianTaskQueueItem]:
    active_filters = filters or TaskQueueFilters()
    tasks = list(db.scalars(select(ReviewTask)))
    items = [build_task_queue_item(db, task, now=now) for task in tasks]
    matching = [item for item in items if _matches_filters(item, active_filters)]
    return sorted(
        matching,
        key=lambda item: (
            -PRIORITY_RANK[item.priority],
            item.opened_at,
            item.task_id,
        ),
    )


def build_dashboard(db: Session, *, now: datetime) -> ClinicianDashboardResponse:
    current_time = _utc(now)
    all_tasks = list(db.scalars(select(ReviewTask)))
    all_items = [build_task_queue_item(db, task, now=current_time) for task in all_tasks]
    start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    active_items = [item for item in all_items if item.status in ACTIVE_TASK_STATUSES]
    summary = ClinicianDashboardSummary(
        unassigned=sum(item.assigned_owner is None for item in active_items),
        awaiting_acknowledgement=sum(item.unacknowledged for item in active_items),
        in_review=sum(item.status is TaskStatus.IN_REVIEW for item in active_items),
        overdue=sum(item.overdue for item in active_items),
        resolved_today=sum(
            task.status is TaskStatus.RESOLVED
            and task.resolved_at is not None
            and start_of_day <= _utc(task.resolved_at) < end_of_day
            for task in all_tasks
        ),
    )
    return ClinicianDashboardResponse(
        generated_at=current_time,
        summary=summary,
        tasks=sorted(
            active_items,
            key=lambda item: (
                -PRIORITY_RANK[item.priority],
                item.opened_at,
                item.task_id,
            ),
        ),
        available_owners=list_clinician_owners(db),
    )


def build_task_list(
    db: Session,
    *,
    now: datetime,
    filters: TaskQueueFilters,
) -> ClinicianTaskListResponse:
    tasks = build_task_queue(db, now=now, filters=filters)
    return ClinicianTaskListResponse(
        generated_at=_utc(now),
        total=len(tasks),
        tasks=tasks,
    )
