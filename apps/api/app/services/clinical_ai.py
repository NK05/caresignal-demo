import json
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    ApprovalStatus,
    DeliveryStatus,
    GenerationType,
    Language,
    MessageDirection,
    PatientMessage,
    PatientProfile,
    TaskStatus,
)
from app.schemas import AIPatientDraft, GroundedCaseBrief
from app.services.clinician_tasks import (
    ClinicianTaskError,
    _audit,
    _require_owner,
    _task,
    build_task_detail,
)

CASE_BRIEF_SAFETY_NOTE = "AI-generated workflow summary; verify against source records."
CASE_INSTRUCTIONS = """Summarise only the supplied synthetic confirmed records and deterministic
rule evidence. Do not diagnose, recommend treatment, assess urgency, or invent facts. Every
source_record_id must be copied from allowed_source_record_ids. Use the required safety note exactly."""
DRAFT_INSTRUCTIONS = """Draft a short patient follow-up using only clinician_outcome and the
requested language. Do not diagnose, prescribe, change medication, assess urgency, or add facts.
Do not tell the patient to start, stop, double, or alter medication. Approval must remain required."""


@dataclass(frozen=True)
class ClinicalAIResult:
    value: GroundedCaseBrief | AIPatientDraft
    request_id: str


class ClinicalAIProvider(Protocol):
    def case_brief(self, payload: dict[str, object]) -> ClinicalAIResult: ...

    def patient_draft(self, payload: dict[str, object]) -> ClinicalAIResult: ...


class OpenAIClinicalProvider:
    def __init__(self, api_key: str | None, model: str, timeout: float) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _parse(
        self,
        instructions: str,
        payload: dict[str, object],
        schema: type[GroundedCaseBrief] | type[AIPatientDraft],
    ) -> ClinicalAIResult:
        if not self.api_key:
            raise RuntimeError("OpenAI clinical drafting is unavailable")
        response = OpenAI(api_key=self.api_key).responses.parse(
            model=self.model,
            instructions=instructions,
            input=json.dumps(payload),
            text_format=schema,
            store=False,
            timeout=self.timeout,
        )
        if response.output_parsed is None:
            raise ValueError("AI response was not parsed")
        return ClinicalAIResult(value=response.output_parsed, request_id=response.id)

    def case_brief(self, payload: dict[str, object]) -> ClinicalAIResult:
        return self._parse(CASE_INSTRUCTIONS, payload, GroundedCaseBrief)

    def patient_draft(self, payload: dict[str, object]) -> ClinicalAIResult:
        return self._parse(DRAFT_INSTRUCTIONS, payload, AIPatientDraft)


def get_clinical_ai_provider() -> ClinicalAIProvider:
    settings = get_settings()
    return OpenAIClinicalProvider(
        settings.openai_api_key,
        settings.openai_model,
        settings.openai_timeout_seconds,
    )


def generate_case_brief(
    db: Session, *, task_id: str, actor, provider: ClinicalAIProvider, now
) -> GroundedCaseBrief:
    task = _task(db, task_id)
    _require_owner(task, actor)
    detail = build_task_detail(db, task_id=task_id, clinician=actor, now=now)
    allowed = {item.reading_id for item in detail.readings} | {
        item.rule_evaluation_id for item in detail.evidence
    }
    result = provider.case_brief(
        {
            "task": detail.task.model_dump(mode="json"),
            "confirmed_readings": [item.model_dump(mode="json") for item in detail.readings],
            "deterministic_evidence": [
                item.model_dump(mode="json") for item in detail.evidence
            ],
            "allowed_source_record_ids": sorted(allowed),
            "required_safety_note": CASE_BRIEF_SAFETY_NOTE,
        }
    )
    brief = result.value
    if not isinstance(brief, GroundedCaseBrief) or not set(
        brief.source_record_ids
    ).issubset(allowed):
        raise ClinicianTaskError("AI case brief referenced unavailable source records")
    _audit(
        db,
        task=task,
        clinician=actor,
        event_type="review_task.ai_case_brief_generated",
        metadata={
            "model_request_id": result.request_id,
            "source_record_ids": brief.source_record_ids,
        },
    )
    db.commit()
    return brief


def generate_patient_draft(
    db: Session,
    *,
    task_id: str,
    actor,
    language: Language,
    clinician_outcome: str,
    provider: ClinicalAIProvider,
) -> PatientMessage:
    task = _task(db, task_id, lock=True)
    _require_owner(task, actor)
    if task.status is not TaskStatus.IN_REVIEW:
        raise ClinicianTaskError("AI drafting requires a task in review")
    patient = db.get(PatientProfile, task.patient_id)
    if patient is None:
        raise ClinicianTaskError("Task patient does not exist")
    result = provider.patient_draft(
        {"clinician_outcome": clinician_outcome, "language": language.value}
    )
    draft = result.value
    if not isinstance(draft, AIPatientDraft) or draft.language != language.value:
        raise ClinicianTaskError("AI draft did not match the requested language")
    message = PatientMessage(
        patient_id=task.patient_id,
        task_id=task.id,
        direction=MessageDirection.OUTBOUND,
        channel=patient.preferred_channel,
        language=language,
        content=draft.content,
        generation_type=GenerationType.AI_DRAFT,
        approval_status=ApprovalStatus.DRAFT,
        delivery_status=DeliveryStatus.NOT_SENT,
    )
    db.add(message)
    db.flush()
    _audit(
        db,
        task=task,
        clinician=actor,
        event_type="review_task.ai_message_drafted",
        metadata={
            "message_id": message.id,
            "model_request_id": result.request_id,
            "language": language.value,
        },
    )
    db.commit()
    return message
