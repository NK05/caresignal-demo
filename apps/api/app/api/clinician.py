from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import CurrentClinician
from app.database import get_db
from app.models import Language, TaskPriority, TaskStatus, utc_now
from app.schemas import (
    AIDraftMessageRequest,
    ClinicianApproveMessageRequest,
    ClinicianContactAttemptRequest,
    ClinicianDashboardResponse,
    ClinicianDraftMessageRequest,
    ClinicianTaskAssignmentRequest,
    ClinicianTaskDetailResponse,
    ClinicianTaskListResponse,
    ClinicianTaskReopenRequest,
    ClinicianTaskResolutionRequest,
    GroundedCaseBrief,
)
from app.services.clinical_ai import (
    ClinicalAIProvider,
    generate_case_brief,
    generate_patient_draft,
    get_clinical_ai_provider,
)
from app.services.clinician_communications import (
    approve_or_send_message,
    create_clinician_message,
    record_contact_attempt,
)
from app.services.clinician_dashboard import (
    TaskQueueFilters,
    build_dashboard,
    build_task_list,
)
from app.services.clinician_tasks import (
    ClinicianTaskError,
    ClinicianTaskNotFoundError,
    acknowledge_task,
    assign_task,
    build_task_detail,
    reopen_task,
    resolve_task,
    start_task_review,
)
from app.services.tasks import TaskTransitionError
from app.services.whatsapp import WhatsAppGateway, get_whatsapp_gateway

router = APIRouter(prefix="/api/v1/clinician", tags=["clinician"])
WhatsAppGatewayDependency = Annotated[WhatsAppGateway, Depends(get_whatsapp_gateway)]
ClinicalAIProviderDependency = Annotated[ClinicalAIProvider, Depends(get_clinical_ai_provider)]


@router.get("/dashboard", response_model=ClinicianDashboardResponse)
def get_clinician_dashboard(
    _clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianDashboardResponse:
    return build_dashboard(db, now=utc_now())


@router.get("/tasks", response_model=ClinicianTaskListResponse)
def get_clinician_tasks(
    _clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
    priority: Annotated[TaskPriority | None, Query()] = None,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    owner: Annotated[str | None, Query(max_length=36)] = None,
    overdue: Annotated[bool | None, Query()] = None,
    language: Annotated[Language | None, Query()] = None,
    medication_adherence_signal: Annotated[bool | None, Query()] = None,
) -> ClinicianTaskListResponse:
    return build_task_list(
        db,
        now=utc_now(),
        filters=TaskQueueFilters(
            priority=priority,
            status=task_status,
            owner=owner,
            overdue=overdue,
            language=language,
            medication_adherence_signal=medication_adherence_signal,
        ),
    )


def _task_error(db: Session, error: ValueError) -> None:
    db.rollback()
    if isinstance(error, ClinicianTaskNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


def _detail(
    db: Session,
    *,
    task_id: str,
    clinician: CurrentClinician,
) -> ClinicianTaskDetailResponse:
    try:
        return build_task_detail(
            db,
            task_id=task_id,
            clinician=clinician,
            now=utc_now(),
        )
    except ClinicianTaskNotFoundError as error:
        _task_error(db, error)


@router.get("/tasks/{task_id}", response_model=ClinicianTaskDetailResponse)
def get_clinician_task(
    task_id: str,
    clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    return _detail(db, task_id=task_id, clinician=clinician)


@router.post("/tasks/{task_id}/case-brief", response_model=GroundedCaseBrief)
def create_case_brief(
    task_id: str,
    clinician: CurrentClinician,
    provider: ClinicalAIProviderDependency,
    db: Annotated[Session, Depends(get_db)],
) -> GroundedCaseBrief:
    try:
        return generate_case_brief(
            db,
            task_id=task_id,
            actor=clinician,
            provider=provider,
            now=utc_now(),
        )
    except ClinicianTaskError as error:
        _task_error(db, error)
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI case brief is temporarily unavailable. Verify the source records directly.",
        ) from error


@router.post("/tasks/{task_id}/ai-draft-message", response_model=ClinicianTaskDetailResponse)
def create_ai_draft(
    task_id: str,
    request: AIDraftMessageRequest,
    clinician: CurrentClinician,
    provider: ClinicalAIProviderDependency,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    try:
        generate_patient_draft(
            db,
            task_id=task_id,
            actor=clinician,
            language=Language(request.language),
            clinician_outcome=request.clinician_outcome,
            provider=provider,
        )
    except ClinicianTaskError as error:
        _task_error(db, error)
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI drafting is temporarily unavailable. Write a clinician-authored message instead.",
        ) from error
    return _detail(db, task_id=task_id, clinician=clinician)


@router.post("/tasks/{task_id}/assign", response_model=ClinicianTaskDetailResponse)
def assign_clinician_task(
    task_id: str,
    request: ClinicianTaskAssignmentRequest,
    clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    try:
        assign_task(
            db,
            task_id=task_id,
            actor=clinician,
            clinician_id=request.clinician_id,
            at=utc_now(),
        )
    except (ClinicianTaskError, TaskTransitionError) as error:
        _task_error(db, error)
    return _detail(db, task_id=task_id, clinician=clinician)


@router.post("/tasks/{task_id}/acknowledge", response_model=ClinicianTaskDetailResponse)
def acknowledge_clinician_task(
    task_id: str,
    clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    try:
        acknowledge_task(db, task_id=task_id, actor=clinician, at=utc_now())
    except ClinicianTaskError as error:
        _task_error(db, error)
    return _detail(db, task_id=task_id, clinician=clinician)


@router.post("/tasks/{task_id}/start-review", response_model=ClinicianTaskDetailResponse)
def start_clinician_task_review(
    task_id: str,
    clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    try:
        start_task_review(db, task_id=task_id, actor=clinician, at=utc_now())
    except (ClinicianTaskError, TaskTransitionError) as error:
        _task_error(db, error)
    return _detail(db, task_id=task_id, clinician=clinician)


@router.post("/tasks/{task_id}/contact-attempts", response_model=ClinicianTaskDetailResponse)
def record_clinician_contact_attempt(
    task_id: str,
    request: ClinicianContactAttemptRequest,
    clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    try:
        record_contact_attempt(
            db,
            task_id=task_id,
            actor=clinician,
            channel=request.channel,
            outcome_code=request.outcome_code,
            note=request.note,
            at=utc_now(),
        )
    except ClinicianTaskError as error:
        _task_error(db, error)
    return _detail(db, task_id=task_id, clinician=clinician)


@router.post("/tasks/{task_id}/draft-message", response_model=ClinicianTaskDetailResponse)
def draft_clinician_message(
    task_id: str,
    request: ClinicianDraftMessageRequest,
    clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    try:
        create_clinician_message(
            db,
            task_id=task_id,
            actor=clinician,
            language=Language(request.language),
            content=request.content,
        )
    except ClinicianTaskError as error:
        _task_error(db, error)
    return _detail(db, task_id=task_id, clinician=clinician)


@router.post("/tasks/{task_id}/approve-message", response_model=ClinicianTaskDetailResponse)
def approve_clinician_message(
    task_id: str,
    request: ClinicianApproveMessageRequest,
    clinician: CurrentClinician,
    whatsapp_gateway: WhatsAppGatewayDependency,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    try:
        approve_or_send_message(
            db,
            task_id=task_id,
            message_id=request.message_id,
            actor=clinician,
            send=request.send,
            at=utc_now(),
            whatsapp_gateway=whatsapp_gateway,
        )
    except ClinicianTaskError as error:
        _task_error(db, error)
    return _detail(db, task_id=task_id, clinician=clinician)


@router.post("/tasks/{task_id}/resolve", response_model=ClinicianTaskDetailResponse)
def resolve_clinician_task(
    task_id: str,
    request: ClinicianTaskResolutionRequest,
    clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    try:
        resolve_task(
            db,
            task_id=task_id,
            actor=clinician,
            outcome_code=request.outcome_code,
            outcome_note=request.outcome_note,
            at=utc_now(),
        )
    except ClinicianTaskError as error:
        _task_error(db, error)
    return _detail(db, task_id=task_id, clinician=clinician)


@router.post("/tasks/{task_id}/reopen", response_model=ClinicianTaskDetailResponse)
def reopen_clinician_task(
    task_id: str,
    request: ClinicianTaskReopenRequest,
    clinician: CurrentClinician,
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianTaskDetailResponse:
    try:
        reopen_task(
            db,
            task_id=task_id,
            actor=clinician,
            reason=request.reason,
            at=utc_now(),
        )
    except ClinicianTaskError as error:
        _task_error(db, error)
    return _detail(db, task_id=task_id, clinician=clinician)
