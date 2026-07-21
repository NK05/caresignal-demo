from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApprovalStatus, PatientMessage, PatientProfile, ReviewTask, TaskStatus, User
from app.schemas import PatientCareMessageResponse, PatientFollowUpResponse, PatientProfileResponse


def patient_profile(db: Session, patient: PatientProfile) -> PatientProfileResponse:
    user = db.get(User, patient.user_id)
    if user is None:
        raise RuntimeError("Patient profile references a missing user")
    return PatientProfileResponse(
        patient_id=patient.id,
        display_name=user.display_name,
        synthetic_identifier=patient.synthetic_identifier,
        preferred_language=user.preferred_language,
        preferred_channel=patient.preferred_channel,
    )


def sent_patient_messages(db: Session, patient: PatientProfile) -> list[PatientCareMessageResponse]:
    messages = list(
        db.scalars(
            select(PatientMessage)
            .where(
                PatientMessage.patient_id == patient.id,
                PatientMessage.approval_status == ApprovalStatus.SENT,
                PatientMessage.sent_at.is_not(None),
                PatientMessage.task_id.is_not(None),
            )
            .order_by(PatientMessage.sent_at.desc(), PatientMessage.id.desc())
        )
    )
    return [
        PatientCareMessageResponse(
            message_id=message.id,
            channel=message.channel,
            language=message.language,
            content=message.content,
            sent_at=message.sent_at,
        )
        for message in messages
        if message.sent_at is not None
    ]


def patient_follow_up(db: Session, patient: PatientProfile) -> PatientFollowUpResponse:
    tasks = list(
        db.scalars(
            select(ReviewTask)
            .where(ReviewTask.patient_id == patient.id)
            .order_by(ReviewTask.updated_at.desc(), ReviewTask.opened_at.desc())
        )
    )
    messages = sent_patient_messages(db, patient)
    latest_message = messages[0] if messages else None
    active = next((task for task in tasks if task.status is not TaskStatus.RESOLVED), None)
    if active is not None:
        if active.status is TaskStatus.OPEN:
            status = "care_team_notified"
            text = "Your care team has been notified for review."
        else:
            status = "review_in_progress"
            text = "Your care team is reviewing your follow-up."
        updated_at = active.updated_at
    elif tasks:
        status = "review_completed"
        text = "Your care team has completed this review."
        updated_at = tasks[0].resolved_at or tasks[0].updated_at
    else:
        status = "no_follow_up"
        text = "No care-team follow-up is currently open."
        updated_at = None
    return PatientFollowUpResponse(
        status=status,
        message=text,
        updated_at=updated_at,
        latest_care_message=latest_message,
    )
