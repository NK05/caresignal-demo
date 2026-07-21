from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def uuid_string() -> str:
    return str(uuid4())


def enum_type(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda values: [value.value for value in values],
    )


class UserRole(StrEnum):
    PATIENT = "patient"
    CLINICIAN = "clinician"
    DEMO_ADMIN = "demo_admin"


class Language(StrEnum):
    ENGLISH = "en"
    SHONA = "sn"
    NDEBELE = "nd"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class Channel(StrEnum):
    APP = "app"
    WHATSAPP_SIMULATOR = "whatsapp_simulator"
    WHATSAPP_SANDBOX = "whatsapp_sandbox"


class SubmissionStatus(StrEnum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    EVALUATED = "evaluated"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class MedicationStatus(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class TaskPriority(StrEnum):
    ROUTINE = "routine"
    WATCH = "watch"
    NEEDS_REVIEW = "needs_review"
    URGENT_REVIEW = "urgent_review"


class TaskStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class GenerationType(StrEnum):
    FIXED_TEMPLATE = "fixed_template"
    AI_DRAFT = "ai_draft"
    CLINICIAN_AUTHORED = "clinician_authored"


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"
    REJECTED = "rejected"


class DeliveryStatus(StrEnum):
    NOT_SENT = "not_sent"
    SENT = "sent"
    DELIVERED = "delivered"
    DELIVERY_FAILED = "delivery_failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole, "user_role"), nullable=False)
    preferred_language: Mapped[Language] = mapped_column(
        enum_type(Language, "language"), default=Language.ENGLISH, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    patient_profile: Mapped["PatientProfile | None"] = relationship(back_populates="user")
    clinician_profile: Mapped["ClinicianProfile | None"] = relationship(back_populates="user")


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    synthetic_identifier: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    preferred_channel: Mapped[Channel] = mapped_column(
        enum_type(Channel, "channel"), default=Channel.APP, nullable=False
    )
    consent_demo_acknowledged: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship(back_populates="patient_profile")


class ClinicianProfile(Base):
    __tablename__ = "clinician_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    display_role: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship(back_populates="clinician_profile")


class ReadingSubmission(Base):
    __tablename__ = "reading_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id"), nullable=False)
    channel: Mapped[Channel] = mapped_column(
        enum_type(Channel, "submission_channel"), nullable=False
    )
    original_message: Mapped[str | None] = mapped_column(Text)
    candidate_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        enum_type(SubmissionStatus, "submission_status"), nullable=False
    )
    language: Mapped[Language] = mapped_column(enum_type(Language, "submission_language"))
    model_request_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class BloodPressureReading(Base):
    __tablename__ = "blood_pressure_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id"), nullable=False)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("reading_submissions.id"), unique=True, nullable=False
    )
    systolic: Mapped[int] = mapped_column(Integer, nullable=False)
    diastolic: Mapped[int] = mapped_column(Integer, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    medication_taken: Mapped[MedicationStatus] = mapped_column(
        enum_type(MedicationStatus, "medication_status"), nullable=False
    )
    missed_medication_reason_code: Mapped[str | None] = mapped_column(String(80))
    context_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RuleEvaluation(Base):
    __tablename__ = "rule_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "reading_id",
            "rule_id",
            "rule_version",
            name="uq_rule_evaluation_reading_rule_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id"), nullable=False)
    reading_id: Mapped[str] = mapped_column(
        ForeignKey("blood_pressure_readings.id"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    triggered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(
        enum_type(TaskPriority, "task_priority"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id"), nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(
        enum_type(TaskPriority, "review_task_priority"), nullable=False
    )
    status: Mapped[TaskStatus] = mapped_column(
        enum_type(TaskStatus, "task_status"), default=TaskStatus.OPEN, nullable=False
    )
    assigned_clinician_id: Mapped[str | None] = mapped_column(ForeignKey("clinician_profiles.id"))
    primary_rule_evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("rule_evaluations.id"), nullable=False
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_code: Mapped[str | None] = mapped_column(String(80))
    outcome_note: Mapped[str | None] = mapped_column(Text)
    reopened_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class TaskEvidence(Base):
    __tablename__ = "task_evidence"

    task_id: Mapped[str] = mapped_column(ForeignKey("review_tasks.id"), primary_key=True)
    rule_evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("rule_evaluations.id"), primary_key=True
    )


class ContactAttempt(Base):
    __tablename__ = "contact_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    task_id: Mapped[str] = mapped_column(ForeignKey("review_tasks.id"), nullable=False)
    clinician_id: Mapped[str] = mapped_column(ForeignKey("clinician_profiles.id"), nullable=False)
    channel: Mapped[Channel] = mapped_column(enum_type(Channel, "contact_channel"), nullable=False)
    outcome_code: Mapped[str] = mapped_column(String(80), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PatientMessage(Base):
    __tablename__ = "patient_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patient_profiles.id"), nullable=False)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("review_tasks.id"))
    direction: Mapped[MessageDirection] = mapped_column(
        enum_type(MessageDirection, "message_direction"), nullable=False
    )
    channel: Mapped[Channel] = mapped_column(enum_type(Channel, "message_channel"), nullable=False)
    language: Mapped[Language] = mapped_column(enum_type(Language, "message_language"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generation_type: Mapped[GenerationType | None] = mapped_column(
        enum_type(GenerationType, "generation_type"), nullable=True
    )
    approval_status: Mapped[ApprovalStatus | None] = mapped_column(
        enum_type(ApprovalStatus, "approval_status"), nullable=True
    )
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        enum_type(DeliveryStatus, "delivery_status"),
        default=DeliveryStatus.NOT_SENT,
        nullable=False,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patient_profiles.id"))
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
