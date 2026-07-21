from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import CurrentPatient
from app.database import get_db
from app.schemas import (
    ConfirmationResponse,
    ConversationActionResponse,
    ConversationalExtractionRequest,
    ConversationalExtractionResponse,
    ConversationSendRequest,
    ConversationSendResponse,
    ConversationStateResponse,
    CorrectionResponse,
    PatientCareMessageResponse,
    PatientFollowUpResponse,
    PatientProfileResponse,
    ReadingResponse,
    StructuredReadingInput,
    SubmissionActionResponse,
    SubmissionResponse,
)
from app.services.ai_extraction import ExtractionProvider, get_extraction_provider
from app.services.ai_extraction import extract_conversational_submission as extract_conversation
from app.services.conversations import (
    act_on_conversation_submission,
    conversation_state,
    send_conversation_message,
)
from app.services.patient_home import patient_follow_up, patient_profile, sent_patient_messages
from app.services.readings import (
    confirm_submission,
    correct_submission,
    create_structured_submission,
    get_owned_submission,
    list_confirmed_readings,
    reject_submission,
)

router = APIRouter(prefix="/api/v1/patient", tags=["patient"])

ExtractionProviderDependency = Annotated[ExtractionProvider, Depends(get_extraction_provider)]


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.get("/profile", response_model=PatientProfileResponse)
def get_profile(
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> PatientProfileResponse:
    return patient_profile(db, patient)


@router.get("/follow-up", response_model=PatientFollowUpResponse)
def get_follow_up(
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> PatientFollowUpResponse:
    return patient_follow_up(db, patient)


@router.get("/messages", response_model=list[PatientCareMessageResponse])
def get_messages(
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> list[PatientCareMessageResponse]:
    return sent_patient_messages(db, patient)


@router.get("/conversation", response_model=ConversationStateResponse)
def get_conversation(
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationStateResponse:
    return conversation_state(
        db,
        patient=patient,
        real_whatsapp_configured=False,
    )


@router.post("/conversation/messages", response_model=ConversationSendResponse)
def send_message(
    request: ConversationSendRequest,
    patient: CurrentPatient,
    provider: ExtractionProviderDependency,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationSendResponse:
    response, _system_message = send_conversation_message(
        db,
        patient=patient,
        actor_user_id=patient.user_id,
        content=request.message,
        provider=provider,
        real_whatsapp_configured=False,
    )
    _commit(db)
    return response


@router.post(
    "/conversation/submissions/{submission_id}/{action}",
    response_model=ConversationActionResponse,
)
def act_on_conversation(
    submission_id: str,
    action: Literal["confirm", "cancel"],
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationActionResponse:
    try:
        response = act_on_conversation_submission(
            db,
            patient=patient,
            actor_user_id=patient.user_id,
            submission_id=submission_id,
            action=action,
            real_whatsapp_configured=False,
        )
        db.commit()
        return response
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/readings", response_model=list[ReadingResponse])
def get_readings(
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> list[ReadingResponse]:
    readings = list_confirmed_readings(db, patient_id=patient.id)
    return [ReadingResponse.model_validate(reading) for reading in readings]


@router.post(
    "/submissions/structured",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_structured_reading(
    request: StructuredReadingInput,
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> SubmissionResponse:
    submission = create_structured_submission(
        db,
        patient=patient,
        actor_user_id=patient.user_id,
        language=patient.user.preferred_language,
        candidate=request,
    )
    _commit(db)
    return SubmissionResponse.model_validate(submission)


@router.post(
    "/submissions/conversational",
    response_model=ConversationalExtractionResponse,
)
def submit_conversational_reading(
    request: ConversationalExtractionRequest,
    patient: CurrentPatient,
    provider: ExtractionProviderDependency,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationalExtractionResponse:
    response = extract_conversation(
        db,
        patient=patient,
        actor_user_id=patient.user_id,
        message=request.message,
        channel=request.channel,
        provider=provider,
    )
    _commit(db)
    return response


@router.get("/submissions/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: str,
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> SubmissionResponse:
    submission = get_owned_submission(
        db,
        submission_id=submission_id,
        patient_id=patient.id,
    )
    return SubmissionResponse.model_validate(submission)


@router.post(
    "/submissions/{submission_id}/confirm",
    response_model=ConfirmationResponse,
)
def confirm_reading(
    submission_id: str,
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> ConfirmationResponse:
    try:
        submission, reading, evaluations, task_sync = confirm_submission(
            db,
            submission_id=submission_id,
            patient=patient,
            actor_user_id=patient.user_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ConfirmationResponse(
        submission=SubmissionResponse.model_validate(submission),
        reading=ReadingResponse.model_validate(reading),
        acknowledgement=(
            "Reading confirmed. Your care team has been notified for review."
            if task_sync.care_team_notified
            else "Reading confirmed."
        ),
        evaluation_count=len(evaluations),
        care_team_notified=task_sync.care_team_notified,
    )


@router.post(
    "/submissions/{submission_id}/correct",
    response_model=CorrectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def correct_reading(
    submission_id: str,
    request: StructuredReadingInput,
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> CorrectionResponse:
    original, revised = correct_submission(
        db,
        submission_id=submission_id,
        patient=patient,
        actor_user_id=patient.user_id,
        language=patient.user.preferred_language,
        candidate=request,
    )
    _commit(db)
    return CorrectionResponse(
        corrected_submission_id=original.id,
        revised_submission=SubmissionResponse.model_validate(revised),
    )


@router.post(
    "/submissions/{submission_id}/reject",
    response_model=SubmissionActionResponse,
)
def reject_reading(
    submission_id: str,
    patient: CurrentPatient,
    db: Annotated[Session, Depends(get_db)],
) -> SubmissionActionResponse:
    submission = reject_submission(
        db,
        submission_id=submission_id,
        patient=patient,
        actor_user_id=patient.user_id,
    )
    _commit(db)
    return SubmissionActionResponse(
        submission_id=submission.id,
        status=submission.status,
    )
