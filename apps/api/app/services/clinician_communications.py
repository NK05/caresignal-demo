from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    ApprovalStatus,
    Channel,
    ClinicianProfile,
    ContactAttempt,
    DeliveryStatus,
    GenerationType,
    Language,
    MessageDirection,
    PatientMessage,
    PatientProfile,
    TaskStatus,
)
from app.services.clinician_tasks import (
    ClinicianTaskError,
    _audit,
    _require_owner,
    _task,
)
from app.services.whatsapp import WhatsAppDeliveryError, WhatsAppGateway


def _require_active_review(task_status: TaskStatus) -> None:
    if task_status is not TaskStatus.IN_REVIEW:
        raise ClinicianTaskError("Contact and message actions require a task in review")


def record_contact_attempt(
    db: Session,
    *,
    task_id: str,
    actor: ClinicianProfile,
    channel: Channel,
    outcome_code: str,
    note: str | None,
    at: datetime,
) -> None:
    task = _task(db, task_id, lock=True)
    _require_owner(task, actor)
    _require_active_review(task.status)
    attempt = ContactAttempt(
        task_id=task.id,
        clinician_id=actor.id,
        channel=channel,
        outcome_code=outcome_code,
        note=note,
        attempted_at=at,
    )
    db.add(attempt)
    db.flush()
    _audit(
        db,
        task=task,
        clinician=actor,
        event_type="review_task.contact_recorded",
        metadata={
            "contact_attempt_id": attempt.id,
            "channel": channel.value,
            "outcome_code": outcome_code,
            "note_recorded": note is not None,
        },
    )
    db.commit()


def create_clinician_message(
    db: Session,
    *,
    task_id: str,
    actor: ClinicianProfile,
    language: Language,
    content: str,
) -> None:
    task = _task(db, task_id, lock=True)
    _require_owner(task, actor)
    _require_active_review(task.status)
    patient_profile = db.get(PatientProfile, task.patient_id)
    if patient_profile is None:
        raise ClinicianTaskError("Task patient does not exist")
    message = PatientMessage(
        patient_id=task.patient_id,
        task_id=task.id,
        direction=MessageDirection.OUTBOUND,
        channel=patient_profile.preferred_channel,
        language=language,
        content=content,
        generation_type=GenerationType.CLINICIAN_AUTHORED,
        approval_status=ApprovalStatus.DRAFT,
        delivery_status=DeliveryStatus.NOT_SENT,
    )
    db.add(message)
    db.flush()
    _audit(
        db,
        task=task,
        clinician=actor,
        event_type="review_task.message_drafted",
        metadata={
            "message_id": message.id,
            "language": language.value,
            "channel": message.channel.value,
            "generation_type": message.generation_type.value,
        },
    )
    db.commit()


def approve_or_send_message(
    db: Session,
    *,
    task_id: str,
    message_id: str,
    actor: ClinicianProfile,
    send: bool,
    at: datetime,
    whatsapp_gateway: WhatsAppGateway | None = None,
) -> None:
    task = _task(db, task_id, lock=True)
    _require_owner(task, actor)
    _require_active_review(task.status)
    message = db.get(PatientMessage, message_id)
    if message is None or message.task_id != task.id or message.patient_id != task.patient_id:
        raise ClinicianTaskError("Patient message does not belong to this task")

    if send:
        if message.approval_status is not ApprovalStatus.APPROVED:
            raise ClinicianTaskError("Message must be approved before it can be sent")
        if message.channel is Channel.WHATSAPP_SANDBOX:
            patient = db.get(PatientProfile, message.patient_id)
            destination = (
                whatsapp_gateway.destination_for_patient(patient)
                if whatsapp_gateway is not None and patient is not None
                else None
            )
            try:
                if whatsapp_gateway is None or destination is None:
                    raise WhatsAppDeliveryError("WhatsApp destination is unavailable")
                provider_message_id = whatsapp_gateway.send_text(
                    destination=destination,
                    content=message.content,
                )
            except WhatsAppDeliveryError:
                message.delivery_status = DeliveryStatus.DELIVERY_FAILED
                event_type = "review_task.message_delivery_failed"
                metadata = {
                    "message_id": message.id,
                    "channel": message.channel.value,
                    "approval_retained": True,
                }
            else:
                message.approval_status = ApprovalStatus.SENT
                message.sent_at = at
                message.delivery_status = DeliveryStatus.SENT
                message.provider_message_id = provider_message_id
                event_type = "review_task.message_sent"
                metadata = {
                    "message_id": message.id,
                    "channel": message.channel.value,
                    "simulated_delivery": False,
                }
        else:
            message.approval_status = ApprovalStatus.SENT
            message.sent_at = at
            message.delivery_status = DeliveryStatus.SENT
            event_type = "review_task.message_sent"
            metadata = {
                "message_id": message.id,
                "channel": message.channel.value,
                "simulated_delivery": True,
            }
    else:
        if message.approval_status is ApprovalStatus.APPROVED:
            return
        if message.approval_status is not ApprovalStatus.DRAFT:
            raise ClinicianTaskError("Only a draft message can be approved")
        message.approval_status = ApprovalStatus.APPROVED
        message.approved_by = actor.user_id
        message.approved_at = at
        event_type = "review_task.message_approved"
        metadata = {"message_id": message.id}

    _audit(
        db,
        task=task,
        clinician=actor,
        event_type=event_type,
        metadata=metadata,
    )
    db.commit()
