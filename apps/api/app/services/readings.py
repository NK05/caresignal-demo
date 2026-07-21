from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    BloodPressureReading,
    Channel,
    Language,
    PatientProfile,
    ReadingSubmission,
    RuleEvaluation,
    SubmissionStatus,
    utc_now,
)
from app.rules.engine import evaluate_confirmed_reading
from app.schemas import StructuredReadingInput
from app.services.tasks import TaskSyncResult, sync_review_tasks


def get_owned_submission(
    db: Session,
    *,
    submission_id: str,
    patient_id: str,
    lock: bool = False,
) -> ReadingSubmission:
    statement = select(ReadingSubmission).where(
        ReadingSubmission.id == submission_id,
        ReadingSubmission.patient_id == patient_id,
    )
    if lock:
        statement = statement.with_for_update()
    submission = db.scalar(statement)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


def _add_audit_event(
    db: Session,
    *,
    actor_user_id: str,
    patient_id: str,
    entity_id: str,
    event_type: str,
    metadata: dict[str, object] | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            patient_id=patient_id,
            entity_type="reading_submission",
            entity_id=entity_id,
            event_type=event_type,
            event_metadata=metadata or {},
        )
    )


def create_structured_submission(
    db: Session,
    *,
    patient: PatientProfile,
    actor_user_id: str,
    language: Language,
    candidate: StructuredReadingInput,
    channel: Channel = Channel.APP,
    original_message: str | None = None,
    model_request_id: str | None = None,
) -> ReadingSubmission:
    submission = ReadingSubmission(
        patient_id=patient.id,
        channel=channel,
        original_message=original_message,
        candidate_payload=candidate.to_candidate_payload(),
        status=SubmissionStatus.PENDING_CONFIRMATION,
        language=language,
        model_request_id=model_request_id,
    )
    db.add(submission)
    db.flush()
    _add_audit_event(
        db,
        actor_user_id=actor_user_id,
        patient_id=patient.id,
        entity_id=submission.id,
        event_type="reading_submission.created",
        metadata={
            "channel": channel.value,
            "requires_confirmation": True,
            "extraction_source": "gpt-5.6" if model_request_id is not None else "structured",
        },
    )
    return submission


def confirm_submission(
    db: Session,
    *,
    submission_id: str,
    patient: PatientProfile,
    actor_user_id: str,
) -> tuple[
    ReadingSubmission,
    BloodPressureReading,
    list[RuleEvaluation],
    TaskSyncResult,
]:
    submission = get_owned_submission(
        db,
        submission_id=submission_id,
        patient_id=patient.id,
        lock=True,
    )
    existing_reading = db.scalar(
        select(BloodPressureReading).where(BloodPressureReading.submission_id == submission.id)
    )
    if existing_reading is not None and submission.status is SubmissionStatus.CONFIRMED:
        evaluations = list(
            db.scalars(
                select(RuleEvaluation).where(RuleEvaluation.reading_id == existing_reading.id)
            )
        )
        if not evaluations:
            evaluations = evaluate_confirmed_reading(
                db,
                reading=existing_reading,
                evaluated_at=utc_now(),
            )
        task_sync = sync_review_tasks(
            db,
            evaluations=evaluations,
            actor_user_id=actor_user_id,
        )
        return submission, existing_reading, evaluations, task_sync
    if submission.status is not SubmissionStatus.PENDING_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Submission cannot be confirmed from status {submission.status.value}",
        )

    payload = dict(submission.candidate_payload)
    if payload.pop("requires_confirmation", None) is not True:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Submission candidate failed confirmation validation",
        )
    try:
        candidate = StructuredReadingInput.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Submission candidate failed confirmation validation",
        ) from exc

    confirmed_at = utc_now()
    reading = BloodPressureReading(
        patient_id=patient.id,
        submission_id=submission.id,
        systolic=candidate.systolic,
        diastolic=candidate.diastolic,
        measured_at=candidate.measured_at,
        medication_taken=candidate.medication_taken,
        missed_medication_reason_code=candidate.missed_medication_reason_code,
        context_codes=candidate.context_codes,
        note=candidate.note,
        confirmed_at=confirmed_at,
    )
    db.add(reading)
    submission.status = SubmissionStatus.CONFIRMED
    db.flush()
    evaluations = evaluate_confirmed_reading(
        db,
        reading=reading,
        evaluated_at=confirmed_at,
    )
    task_sync = sync_review_tasks(
        db,
        evaluations=evaluations,
        actor_user_id=actor_user_id,
    )
    _add_audit_event(
        db,
        actor_user_id=actor_user_id,
        patient_id=patient.id,
        entity_id=submission.id,
        event_type="blood_pressure_reading.confirmed",
        metadata={
            "reading_id": reading.id,
            "channel": submission.channel.value,
            "rule_evaluation_count": len(evaluations),
            "review_task_count": len(task_sync.tasks),
        },
    )
    return submission, reading, evaluations, task_sync


def correct_submission(
    db: Session,
    *,
    submission_id: str,
    patient: PatientProfile,
    actor_user_id: str,
    language: Language,
    candidate: StructuredReadingInput,
) -> tuple[ReadingSubmission, ReadingSubmission]:
    original = get_owned_submission(
        db,
        submission_id=submission_id,
        patient_id=patient.id,
        lock=True,
    )
    if original.status is not SubmissionStatus.PENDING_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Submission cannot be corrected from status {original.status.value}",
        )

    original.status = SubmissionStatus.CORRECTED
    original.candidate_payload = {}
    original.original_message = None
    revised = create_structured_submission(
        db,
        patient=patient,
        actor_user_id=actor_user_id,
        language=language,
        candidate=candidate,
        channel=original.channel,
    )
    _add_audit_event(
        db,
        actor_user_id=actor_user_id,
        patient_id=patient.id,
        entity_id=original.id,
        event_type="reading_submission.corrected",
        metadata={"revised_submission_id": revised.id},
    )
    return original, revised


def reject_submission(
    db: Session,
    *,
    submission_id: str,
    patient: PatientProfile,
    actor_user_id: str,
) -> ReadingSubmission:
    submission = get_owned_submission(
        db,
        submission_id=submission_id,
        patient_id=patient.id,
        lock=True,
    )
    if submission.status is not SubmissionStatus.PENDING_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Submission cannot be rejected from status {submission.status.value}",
        )

    submission.status = SubmissionStatus.REJECTED
    submission.candidate_payload = {}
    submission.original_message = None
    _add_audit_event(
        db,
        actor_user_id=actor_user_id,
        patient_id=patient.id,
        entity_id=submission.id,
        event_type="reading_submission.rejected",
        metadata={"clinical_values_retained": False},
    )
    return submission


def list_confirmed_readings(db: Session, *, patient_id: str) -> list[BloodPressureReading]:
    return list(
        db.scalars(
            select(BloodPressureReading)
            .where(BloodPressureReading.patient_id == patient_id)
            .order_by(BloodPressureReading.measured_at.desc())
        )
    )
