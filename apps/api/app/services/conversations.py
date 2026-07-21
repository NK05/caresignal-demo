from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content import patient_text
from app.models import (
    ApprovalStatus,
    Channel,
    DeliveryStatus,
    GenerationType,
    MessageDirection,
    PatientMessage,
    PatientProfile,
    ReadingSubmission,
    SubmissionStatus,
    utc_now,
)
from app.schemas import (
    ConversationActionResponse,
    ConversationMessageResponse,
    ConversationSendResponse,
    ConversationStateResponse,
    SubmissionResponse,
)
from app.services.ai_extraction import ExtractionProvider, extract_conversational_submission
from app.services.readings import confirm_submission, get_owned_submission, reject_submission

CONVERSATION_CHANNELS = (Channel.WHATSAPP_SIMULATOR, Channel.WHATSAPP_SANDBOX)
CONFIRM_COMMANDS = frozenset(
    {
        "confirm",
        "confirm reading",
        "yes",
        "save",
        "simbisa",
        "simbisa kuverengwa",
        "qinisekisa",
        "qinisekisa ukubalwa",
    }
)
CANCEL_COMMANDS = frozenset(
    {
        "cancel",
        "cancel reading",
        "reject",
        "kanzura",
        "kanzura kuverengwa",
        "khansela",
        "khansela ukubalwa",
    }
)
CORRECT_COMMANDS = frozenset({"correct", "correct reading", "edit", "gadzirisa", "lungisa"})


def _message_type(message: PatientMessage) -> str:
    if message.direction is MessageDirection.INBOUND:
        return "patient"
    if message.task_id is not None:
        return "care_team"
    return "system"


def conversation_state(
    db: Session,
    *,
    patient: PatientProfile,
    real_whatsapp_configured: bool,
) -> ConversationStateResponse:
    messages = list(
        db.scalars(
            select(PatientMessage)
            .where(
                PatientMessage.patient_id == patient.id,
                PatientMessage.channel.in_(CONVERSATION_CHANNELS),
            )
            .order_by(PatientMessage.created_at.asc(), PatientMessage.id.asc())
        )
    )
    pending = db.scalar(
        select(ReadingSubmission)
        .where(
            ReadingSubmission.patient_id == patient.id,
            ReadingSubmission.channel.in_(CONVERSATION_CHANNELS),
            ReadingSubmission.status == SubmissionStatus.PENDING_CONFIRMATION,
        )
        .order_by(ReadingSubmission.created_at.desc(), ReadingSubmission.id.desc())
        .limit(1)
    )
    return ConversationStateResponse(
        preferred_language=patient.user.preferred_language,
        channel_label=(
            "WhatsApp test integration"
            if real_whatsapp_configured
            else "WhatsApp-compatible simulator"
        ),
        real_whatsapp_configured=real_whatsapp_configured,
        messages=[
            ConversationMessageResponse(
                message_id=message.id,
                direction=message.direction,
                channel=message.channel,
                language=message.language,
                content=message.content,
                message_type=_message_type(message),
                delivery_status=message.delivery_status,
                created_at=message.created_at,
            )
            for message in messages
        ],
        pending_submission=(SubmissionResponse.model_validate(pending) if pending else None),
    )


def _inbound_message(
    db: Session,
    *,
    patient: PatientProfile,
    content: str,
    channel: Channel,
    provider_message_id: str | None,
    at: datetime,
) -> PatientMessage:
    message = PatientMessage(
        patient_id=patient.id,
        direction=MessageDirection.INBOUND,
        channel=channel,
        language=patient.user.preferred_language,
        content=content,
        generation_type=None,
        approval_status=None,
        sent_at=at,
        delivery_status=DeliveryStatus.DELIVERED,
        provider_message_id=provider_message_id,
        created_at=at,
        updated_at=at,
    )
    db.add(message)
    db.flush()
    return message


def _system_message(
    db: Session,
    *,
    patient: PatientProfile,
    content: str,
    channel: Channel,
    delivered: bool,
    at: datetime,
) -> PatientMessage:
    message_time = at + timedelta(microseconds=1)
    message = PatientMessage(
        patient_id=patient.id,
        direction=MessageDirection.OUTBOUND,
        channel=channel,
        language=patient.user.preferred_language,
        content=content,
        generation_type=GenerationType.FIXED_TEMPLATE,
        approval_status=ApprovalStatus.SENT,
        sent_at=message_time if delivered else None,
        delivery_status=DeliveryStatus.SENT if delivered else DeliveryStatus.NOT_SENT,
        created_at=message_time,
        updated_at=message_time,
    )
    db.add(message)
    db.flush()
    return message


def send_conversation_message(
    db: Session,
    *,
    patient: PatientProfile,
    actor_user_id: str,
    content: str,
    provider: ExtractionProvider,
    channel: Channel = Channel.WHATSAPP_SIMULATOR,
    provider_message_id: str | None = None,
    real_whatsapp_configured: bool = False,
    at: datetime | None = None,
) -> tuple[ConversationSendResponse, PatientMessage | None]:
    timestamp = at or utc_now()
    if provider_message_id is not None:
        existing = db.scalar(
            select(PatientMessage).where(PatientMessage.provider_message_id == provider_message_id)
        )
        if existing is not None:
            return (
                ConversationSendResponse(
                    conversation=conversation_state(
                        db,
                        patient=patient,
                        real_whatsapp_configured=real_whatsapp_configured,
                    ),
                    extraction=None,
                    duplicate_provider_message=True,
                ),
                None,
            )

    _inbound_message(
        db,
        patient=patient,
        content=content,
        channel=channel,
        provider_message_id=provider_message_id,
        at=timestamp,
    )
    pending = db.scalar(
        select(ReadingSubmission)
        .where(
            ReadingSubmission.patient_id == patient.id,
            ReadingSubmission.channel.in_(CONVERSATION_CHANNELS),
            ReadingSubmission.status == SubmissionStatus.PENDING_CONFIRMATION,
        )
        .order_by(ReadingSubmission.created_at.desc(), ReadingSubmission.id.desc())
        .limit(1)
    )
    command = " ".join(content.lower().strip().split())
    if pending is not None:
        acknowledgement: str
        if command in CONFIRM_COMMANDS:
            _submission, _reading, _evaluations, task_sync = confirm_submission(
                db,
                submission_id=pending.id,
                patient=patient,
                actor_user_id=actor_user_id,
            )
            acknowledgement = patient_text(
                patient.user.preferred_language,
                "confirmed_notified" if task_sync.care_team_notified else "confirmed",
            )
        elif command in CANCEL_COMMANDS | CORRECT_COMMANDS:
            reject_submission(
                db,
                submission_id=pending.id,
                patient=patient,
                actor_user_id=actor_user_id,
            )
            acknowledgement = patient_text(
                patient.user.preferred_language,
                "corrected" if command in CORRECT_COMMANDS else "cancelled",
            )
        else:
            acknowledgement = patient_text(patient.user.preferred_language, "pending")
        system_message = _system_message(
            db,
            patient=patient,
            content=acknowledgement,
            channel=channel,
            delivered=channel is Channel.WHATSAPP_SIMULATOR,
            at=timestamp,
        )
        return (
            ConversationSendResponse(
                conversation=conversation_state(
                    db,
                    patient=patient,
                    real_whatsapp_configured=real_whatsapp_configured,
                ),
                extraction=None,
            ),
            system_message,
        )

    extraction = extract_conversational_submission(
        db,
        patient=patient,
        actor_user_id=actor_user_id,
        message=content,
        channel=channel,
        provider=provider,
        received_at=timestamp,
    )
    system_message = _system_message(
        db,
        patient=patient,
        content=extraction.clarification_message,
        channel=channel,
        delivered=channel is Channel.WHATSAPP_SIMULATOR,
        at=timestamp,
    )
    return (
        ConversationSendResponse(
            conversation=conversation_state(
                db,
                patient=patient,
                real_whatsapp_configured=real_whatsapp_configured,
            ),
            extraction=extraction,
        ),
        system_message,
    )


def act_on_conversation_submission(
    db: Session,
    *,
    patient: PatientProfile,
    actor_user_id: str,
    submission_id: str,
    action: str,
    real_whatsapp_configured: bool,
    at: datetime | None = None,
) -> ConversationActionResponse:
    timestamp = at or utc_now()
    submission = get_owned_submission(
        db,
        submission_id=submission_id,
        patient_id=patient.id,
        lock=True,
    )
    if submission.channel not in CONVERSATION_CHANNELS:
        raise ValueError("Submission does not belong to the conversation channel")

    if action == "confirm":
        _inbound_message(
            db,
            patient=patient,
            content=patient_text(patient.user.preferred_language, "confirm_command"),
            channel=submission.channel,
            provider_message_id=None,
            at=timestamp,
        )
        _submission, _reading, _evaluations, task_sync = confirm_submission(
            db,
            submission_id=submission.id,
            patient=patient,
            actor_user_id=actor_user_id,
        )
        acknowledgement = patient_text(
            patient.user.preferred_language,
            "confirmed_notified" if task_sync.care_team_notified else "confirmed",
        )
        care_team_notified = task_sync.care_team_notified
    elif action == "cancel":
        _inbound_message(
            db,
            patient=patient,
            content=patient_text(patient.user.preferred_language, "cancel_command"),
            channel=submission.channel,
            provider_message_id=None,
            at=timestamp,
        )
        reject_submission(
            db,
            submission_id=submission.id,
            patient=patient,
            actor_user_id=actor_user_id,
        )
        acknowledgement = patient_text(patient.user.preferred_language, "cancelled")
        care_team_notified = False
    else:
        raise ValueError("Unsupported conversation action")

    _system_message(
        db,
        patient=patient,
        content=acknowledgement,
        channel=submission.channel,
        delivered=submission.channel is Channel.WHATSAPP_SIMULATOR,
        at=timestamp,
    )
    return ConversationActionResponse(
        conversation=conversation_state(
            db,
            patient=patient,
            real_whatsapp_configured=real_whatsapp_configured,
        ),
        acknowledgement=acknowledgement,
        care_team_notified=care_team_notified,
    )
