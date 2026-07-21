from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import get_settings
from app.models import (
    ApprovalStatus,
    Channel,
    DeliveryStatus,
    GenerationType,
    Language,
    MedicationStatus,
    MessageDirection,
    SubmissionStatus,
    TaskPriority,
    TaskStatus,
    UserRole,
)

SUPPORTED_CONTEXT_CODES = frozenset(
    {
        "rested",
        "after_activity",
        "recent_caffeine",
        "feeling_stressed",
        "feeling_unwell",
    }
)
SUPPORTED_MISSED_MEDICATION_REASONS = frozenset(
    {
        "refill_unavailable",
        "forgot",
        "side_effect_concern",
        "other",
        "prefer_not_to_say",
    }
)


class DemoResetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    synthetic_data: bool
    counts: dict[str, int]


class EscalationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed"] = "completed"
    synthetic_data: Literal[True] = True
    overdue_active_tasks: int
    newly_escalated_tasks: int
    task_ids: list[str]


class DemoSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=36, max_length=36)


class DemoSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_token: str
    user_id: str
    display_name: str
    role: UserRole
    preferred_language: Language
    synthetic_data: Literal[True] = True
    non_production_auth: Literal[True] = True


class StructuredReadingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    systolic: int = Field(strict=True)
    diastolic: int = Field(strict=True)
    measured_at: datetime
    medication_taken: MedicationStatus
    missed_medication_reason_code: str | None = Field(default=None, max_length=80)
    context_codes: list[str] = Field(default_factory=list, max_length=5)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("measured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("measured_at must include a timezone offset")
        return value

    @field_validator("context_codes")
    @classmethod
    def validate_context_codes(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("context_codes must not contain duplicates")
        unsupported = sorted(set(value) - SUPPORTED_CONTEXT_CODES)
        if unsupported:
            raise ValueError(f"unsupported context_codes: {', '.join(unsupported)}")
        return value

    @model_validator(mode="after")
    def validate_candidate(self) -> "StructuredReadingInput":
        settings = get_settings()
        if (
            not settings.caresignal_bp_systolic_min
            <= self.systolic
            <= (settings.caresignal_bp_systolic_max)
        ):
            raise ValueError("systolic is outside the configured plausibility bounds")
        if (
            not settings.caresignal_bp_diastolic_min
            <= self.diastolic
            <= (settings.caresignal_bp_diastolic_max)
        ):
            raise ValueError("diastolic is outside the configured plausibility bounds")
        if self.medication_taken is MedicationStatus.UNKNOWN:
            raise ValueError("structured entry does not accept unknown medication status")
        if (
            self.missed_medication_reason_code is not None
            and self.missed_medication_reason_code not in SUPPORTED_MISSED_MEDICATION_REASONS
        ):
            raise ValueError("unsupported missed_medication_reason_code")
        if (
            self.medication_taken is not MedicationStatus.NO
            and self.missed_medication_reason_code is not None
        ):
            raise ValueError("a missed medication reason requires medication_taken=no")
        return self

    def to_candidate_payload(self) -> dict[str, Any]:
        return {
            **self.model_dump(mode="json"),
            "requires_confirmation": True,
        }


class ConversationalExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=1000)
    channel: Literal[Channel.WHATSAPP_SIMULATOR] = Channel.WHATSAPP_SIMULATOR

    @field_validator("message")
    @classmethod
    def normalise_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class ReadingExtraction(BaseModel):
    """Strict GPT-5.6 output contract; clinical validation happens separately."""

    model_config = ConfigDict(extra="forbid")

    language: Language
    systolic: int = Field(strict=True)
    diastolic: int = Field(strict=True)
    measurement_time_text: str | None = Field(default=None, max_length=100)
    medication_taken: MedicationStatus
    missed_medication_reason: (
        Literal[
            "refill_unavailable",
            "forgot",
            "side_effect_concern",
            "other",
            "prefer_not_to_say",
        ]
        | None
    ) = None
    context_codes: list[str] = Field(default_factory=list, max_length=5)
    unstructured_note: str | None = Field(default=None, max_length=500)
    missing_fields: list[str] = Field(default_factory=list, max_length=8)
    ambiguities: list[str] = Field(default_factory=list, max_length=8)
    requires_confirmation: Literal[True] = True

    @field_validator("context_codes", "missing_fields", "ambiguities")
    @classmethod
    def require_unique_list_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("list values must not contain duplicates")
        return value


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    patient_id: str
    channel: Channel
    candidate_payload: dict[str, Any]
    status: SubmissionStatus
    language: Language
    created_at: datetime
    updated_at: datetime


class ConversationalExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "ready_for_confirmation",
        "clarification_required",
        "fallback_required",
    ]
    extraction: ReadingExtraction | None
    submission: SubmissionResponse | None
    clarification_message: str
    fallback_to_structured_form: bool
    synthetic_data: Literal[True] = True
    non_diagnostic: Literal[True] = True


class ConversationSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def normalise_conversation_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    direction: MessageDirection
    channel: Channel
    language: Language
    content: str
    message_type: Literal["patient", "system", "care_team"]
    delivery_status: DeliveryStatus
    created_at: datetime


class ConversationStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_label: str
    preferred_language: Language
    real_whatsapp_configured: bool
    synthetic_data: Literal[True] = True
    non_diagnostic: Literal[True] = True
    messages: list[ConversationMessageResponse]
    pending_submission: SubmissionResponse | None


class ConversationSendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: ConversationStateResponse
    extraction: ConversationalExtractionResponse | None
    duplicate_provider_message: bool = False


class ConversationActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: ConversationStateResponse
    acknowledgement: str
    care_team_notified: bool


class ReadingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    patient_id: str
    submission_id: str
    systolic: int
    diastolic: int
    measured_at: datetime
    medication_taken: MedicationStatus
    missed_medication_reason_code: str | None
    context_codes: list[str]
    note: str | None
    confirmed_at: datetime


class ConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission: SubmissionResponse
    reading: ReadingResponse
    acknowledgement: str
    rules_evaluated: Literal[True] = True
    evaluation_count: int = Field(ge=1)
    care_team_notified: bool


class CorrectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corrected_submission_id: str
    revised_submission: SubmissionResponse


class SubmissionActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: str
    status: SubmissionStatus


class PatientProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str
    display_name: str
    synthetic_identifier: str
    preferred_language: Language
    preferred_channel: Channel
    synthetic_data: Literal[True] = True


class PatientCareMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    channel: Channel
    language: Language
    content: str
    sent_at: datetime


class PatientFollowUpResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "no_follow_up",
        "care_team_notified",
        "review_in_progress",
        "review_completed",
    ]
    message: str
    updated_at: datetime | None
    latest_care_message: PatientCareMessageResponse | None


class ClinicianOwnerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinician_id: str
    display_name: str
    display_role: str


class DashboardReadingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reading_id: str
    systolic: int
    diastolic: int
    measured_at: datetime
    medication_taken: MedicationStatus


class ClinicianTaskQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    patient_id: str
    patient_synthetic_identifier: str
    patient_display_name: str
    preferred_language: Language
    preferred_channel: Channel
    priority: TaskPriority
    status: TaskStatus
    flag_title: str
    flag_reason: str
    rule_version: str
    latest_reading: DashboardReadingSummary
    medication_adherence_signal: bool
    assigned_owner: ClinicianOwnerSummary | None
    evidence_count: int
    opened_at: datetime
    due_at: datetime | None
    task_age_minutes: int
    overdue: bool
    unacknowledged: bool


class ClinicianDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unassigned: int
    awaiting_acknowledgement: int
    in_review: int
    overdue: int
    resolved_today: int


class ClinicianDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    synthetic_data: Literal[True] = True
    summary: ClinicianDashboardSummary
    tasks: list[ClinicianTaskQueueItem]
    available_owners: list[ClinicianOwnerSummary]


class ClinicianTaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    synthetic_data: Literal[True] = True
    total: int
    tasks: list[ClinicianTaskQueueItem]


class ClinicianTaskReadingDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reading_id: str
    systolic: int
    diastolic: int
    measured_at: datetime
    confirmed_at: datetime
    medication_taken: MedicationStatus
    missed_medication_reason_code: str | None
    context_codes: list[str]
    note: str | None


class ClinicianTaskEvidenceDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_evaluation_id: str
    reading_id: str
    rule_id: str
    rule_version: str
    priority: TaskPriority
    title: str
    reason: str
    source_reference: str
    evaluated_at: datetime
    observed_values: list[dict[str, Any]]


class ClinicianTaskAllowedActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_assign: bool
    can_unassign: bool
    can_acknowledge: bool
    can_start_review: bool
    can_return_to_assigned: bool
    can_resolve: bool
    can_reopen: bool
    can_record_contact: bool
    can_draft_message: bool


class ClinicianContactAttemptDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_attempt_id: str
    clinician: ClinicianOwnerSummary
    channel: Channel
    outcome_code: str
    note: str | None
    attempted_at: datetime


class ClinicianPatientMessageDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    channel: Channel
    language: Language
    content: str
    generation_type: GenerationType
    approval_status: ApprovalStatus
    approved_by: str | None
    approved_at: datetime | None
    sent_at: datetime | None
    delivery_status: DeliveryStatus
    created_at: datetime


class ClinicianAuditEventDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_event_id: str
    actor_display_name: str
    event_type: str
    metadata: dict[str, Any]
    created_at: datetime


class ClinicianTaskDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    synthetic_data: Literal[True] = True
    task: ClinicianTaskQueueItem
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    outcome_code: str | None
    outcome_note: str | None
    reopened_count: int
    readings: list[ClinicianTaskReadingDetail]
    evidence: list[ClinicianTaskEvidenceDetail]
    available_owners: list[ClinicianOwnerSummary]
    current_clinician: ClinicianOwnerSummary
    allowed_actions: ClinicianTaskAllowedActions
    contact_attempts: list[ClinicianContactAttemptDetail]
    messages: list[ClinicianPatientMessageDetail]
    audit_events: list[ClinicianAuditEventDetail]


class ClinicianTaskAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinician_id: str | None = Field(min_length=36, max_length=36)


class ClinicianTaskResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_code: Literal[
        "review_completed",
        "follow_up_planned",
        "unable_to_reach",
        "duplicate_or_invalid_record",
    ]
    outcome_note: str | None = Field(default=None, max_length=1000)

    @field_validator("outcome_note")
    @classmethod
    def normalise_outcome_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ClinicianTaskReopenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalise_reopen_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank")
        return stripped


class ClinicianContactAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Channel
    outcome_code: Literal["reached", "no_answer", "message_left", "follow_up_scheduled"]
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note")
    @classmethod
    def normalise_contact_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ClinicianDraftMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["en", "sn", "nd"]
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def normalise_message_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be blank")
        return stripped


class ClinicianApproveMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=36, max_length=36)
    send: bool = False


class GroundedCaseBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1200)
    timeline_points: list[str] = Field(max_length=12)
    rule_explanation: str = Field(min_length=1, max_length=1200)
    adherence_context: str | None = Field(default=None, max_length=500)
    missing_information: list[str] = Field(max_length=12)
    source_record_ids: list[str] = Field(min_length=1, max_length=50)
    safety_note: Literal["AI-generated workflow summary; verify against source records."]


class AIPatientDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["en", "sn", "nd"]
    content: str = Field(min_length=1, max_length=2000)
    requires_clinician_approval: Literal[True]


class AIDraftMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["en", "sn", "nd"]
    clinician_outcome: str = Field(min_length=3, max_length=1000)
