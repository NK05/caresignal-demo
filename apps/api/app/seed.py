from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    BloodPressureReading,
    Channel,
    ClinicianProfile,
    ContactAttempt,
    Language,
    MedicationStatus,
    PatientMessage,
    PatientProfile,
    ReadingSubmission,
    ReviewTask,
    RuleEvaluation,
    SubmissionStatus,
    TaskEvidence,
    TaskPriority,
    TaskStatus,
    User,
    UserRole,
)

USER_IDS = {
    "tariro": "10000000-0000-4000-8000-000000000001",
    "rudo": "10000000-0000-4000-8000-000000000002",
    "tawanda": "10000000-0000-4000-8000-000000000003",
    "nomsa": "10000000-0000-4000-8000-000000000004",
    "doctor": "20000000-0000-4000-8000-000000000001",
    "nurse": "20000000-0000-4000-8000-000000000002",
    "admin": "30000000-0000-4000-8000-000000000001",
}

PATIENT_IDS = {
    "tariro": "11000000-0000-4000-8000-000000000001",
    "rudo": "11000000-0000-4000-8000-000000000002",
    "tawanda": "11000000-0000-4000-8000-000000000003",
    "nomsa": "11000000-0000-4000-8000-000000000004",
}

CLINICIAN_IDS = {
    "doctor": "21000000-0000-4000-8000-000000000001",
    "nurse": "21000000-0000-4000-8000-000000000002",
}


def _reading_bundle(
    *,
    key: str,
    patient_key: str,
    systolic: int,
    diastolic: int,
    measured_at: datetime,
    language: Language,
    channel: Channel,
    medication_taken: MedicationStatus,
    missed_reason: str | None = None,
) -> tuple[ReadingSubmission, BloodPressureReading]:
    submission_id = f"40000000-0000-4000-8000-{key:0>12}"
    reading_id = f"41000000-0000-4000-8000-{key:0>12}"
    submission = ReadingSubmission(
        id=submission_id,
        patient_id=PATIENT_IDS[patient_key],
        channel=channel,
        candidate_payload={
            "systolic": systolic,
            "diastolic": diastolic,
            "medication_taken": medication_taken.value,
            "requires_confirmation": True,
        },
        status=SubmissionStatus.EVALUATED,
        language=language,
    )
    reading = BloodPressureReading(
        id=reading_id,
        patient_id=PATIENT_IDS[patient_key],
        submission_id=submission_id,
        systolic=systolic,
        diastolic=diastolic,
        measured_at=measured_at,
        medication_taken=medication_taken,
        missed_medication_reason_code=missed_reason,
        context_codes=[],
        confirmed_at=measured_at + timedelta(minutes=1),
    )
    return submission, reading


def seed_demo_data(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Create the fixed synthetic dataset used by local development and judging."""

    now = now or datetime.now(UTC)

    users = [
        User(
            id=USER_IDS["tariro"],
            display_name="Tariro Moyo",
            role=UserRole.PATIENT,
            preferred_language=Language.ENGLISH,
        ),
        User(
            id=USER_IDS["rudo"],
            display_name="Rudo Ncube",
            role=UserRole.PATIENT,
            preferred_language=Language.NDEBELE,
        ),
        User(
            id=USER_IDS["tawanda"],
            display_name="Tawanda Chikore",
            role=UserRole.PATIENT,
            preferred_language=Language.SHONA,
        ),
        User(
            id=USER_IDS["nomsa"],
            display_name="Nomsa Dube",
            role=UserRole.PATIENT,
            preferred_language=Language.NDEBELE,
        ),
        User(
            id=USER_IDS["doctor"],
            display_name="Dr Chipo Moyo",
            role=UserRole.CLINICIAN,
            preferred_language=Language.ENGLISH,
        ),
        User(
            id=USER_IDS["nurse"],
            display_name="Nurse Thandi Ncube",
            role=UserRole.CLINICIAN,
            preferred_language=Language.NDEBELE,
        ),
        User(
            id=USER_IDS["admin"],
            display_name="CareSignal Demo Admin",
            role=UserRole.DEMO_ADMIN,
            preferred_language=Language.ENGLISH,
        ),
    ]
    db.add_all(users)
    db.flush()

    patients = [
        PatientProfile(
            id=PATIENT_IDS["tariro"],
            user_id=USER_IDS["tariro"],
            synthetic_identifier="CS-PAT-001",
            preferred_channel=Channel.APP,
        ),
        PatientProfile(
            id=PATIENT_IDS["rudo"],
            user_id=USER_IDS["rudo"],
            synthetic_identifier="CS-PAT-002",
            preferred_channel=Channel.WHATSAPP_SIMULATOR,
        ),
        PatientProfile(
            id=PATIENT_IDS["tawanda"],
            user_id=USER_IDS["tawanda"],
            synthetic_identifier="CS-PAT-003",
            preferred_channel=Channel.WHATSAPP_SIMULATOR,
        ),
        PatientProfile(
            id=PATIENT_IDS["nomsa"],
            user_id=USER_IDS["nomsa"],
            synthetic_identifier="CS-PAT-004",
            preferred_channel=Channel.WHATSAPP_SIMULATOR,
        ),
    ]
    clinicians = [
        ClinicianProfile(
            id=CLINICIAN_IDS["doctor"],
            user_id=USER_IDS["doctor"],
            display_role="Doctor",
        ),
        ClinicianProfile(
            id=CLINICIAN_IDS["nurse"],
            user_id=USER_IDS["nurse"],
            display_role="Chronic-care nurse",
        ),
    ]
    db.add_all([*patients, *clinicians])
    db.flush()

    reading_specs = [
        {
            "key": "1",
            "patient_key": "tariro",
            "systolic": 128,
            "diastolic": 82,
            "measured_at": now - timedelta(days=1),
            "language": Language.ENGLISH,
            "channel": Channel.APP,
            "medication_taken": MedicationStatus.YES,
        },
        {
            "key": "2",
            "patient_key": "rudo",
            "systolic": 158,
            "diastolic": 99,
            "measured_at": now - timedelta(days=5),
            "language": Language.NDEBELE,
            "channel": Channel.WHATSAPP_SIMULATOR,
            "medication_taken": MedicationStatus.YES,
        },
        {
            "key": "3",
            "patient_key": "rudo",
            "systolic": 161,
            "diastolic": 101,
            "measured_at": now - timedelta(days=3),
            "language": Language.NDEBELE,
            "channel": Channel.WHATSAPP_SIMULATOR,
            "medication_taken": MedicationStatus.YES,
        },
        {
            "key": "4",
            "patient_key": "rudo",
            "systolic": 168,
            "diastolic": 105,
            "measured_at": now - timedelta(days=1),
            "language": Language.NDEBELE,
            "channel": Channel.WHATSAPP_SIMULATOR,
            "medication_taken": MedicationStatus.YES,
        },
        {
            "key": "5",
            "patient_key": "tawanda",
            "systolic": 152,
            "diastolic": 96,
            "measured_at": now - timedelta(hours=10),
            "language": Language.SHONA,
            "channel": Channel.WHATSAPP_SIMULATOR,
            "medication_taken": MedicationStatus.NO,
            "missed_reason": "refill_unavailable",
        },
        {
            "key": "6",
            "patient_key": "nomsa",
            "systolic": 186,
            "diastolic": 122,
            "measured_at": now - timedelta(hours=2),
            "language": Language.NDEBELE,
            "channel": Channel.WHATSAPP_SIMULATOR,
            "medication_taken": MedicationStatus.YES,
        },
    ]
    bundles = [_reading_bundle(**spec) for spec in reading_specs]
    db.add_all([submission for submission, _reading in bundles])
    db.flush()
    db.add_all([reading for _submission, reading in bundles])
    db.flush()

    nomsa_reading = bundles[-1][1]
    evaluation = RuleEvaluation(
        id="50000000-0000-4000-8000-000000000001",
        patient_id=PATIENT_IDS["nomsa"],
        reading_id=nomsa_reading.id,
        rule_id="demo-single-reading-review",
        rule_version="demo-0.1",
        triggered=True,
        priority=TaskPriority.URGENT_REVIEW,
        reason="Illustrative demo rule requires prompt clinician review of this confirmed reading.",
        evidence={"reading_ids": [nomsa_reading.id], "synthetic": True},
        source_reference=(
            "Illustrative prototype configuration—not clinically validated for deployment"
        ),
        evaluated_at=now - timedelta(hours=2),
    )
    task = ReviewTask(
        id="51000000-0000-4000-8000-000000000001",
        patient_id=PATIENT_IDS["nomsa"],
        priority=TaskPriority.URGENT_REVIEW,
        status=TaskStatus.OPEN,
        primary_rule_evaluation_id=evaluation.id,
        opened_at=now - timedelta(hours=2),
        due_at=now - timedelta(minutes=30),
    )
    db.add(evaluation)
    db.flush()
    db.add(task)
    db.flush()
    db.add(TaskEvidence(task_id=task.id, rule_evaluation_id=evaluation.id))
    db.add(
        AuditEvent(
            actor_user_id=USER_IDS["admin"],
            patient_id=None,
            entity_type="demo_dataset",
            entity_id=USER_IDS["admin"],
            event_type="demo.seeded",
            event_metadata={"synthetic": True, "schema_version": "0.1"},
            created_at=now,
        )
    )
    db.flush()
    return demo_counts(db)


def demo_counts(db: Session) -> dict[str, int]:
    models = {
        "users": User,
        "patients": PatientProfile,
        "clinicians": ClinicianProfile,
        "submissions": ReadingSubmission,
        "readings": BloodPressureReading,
        "rule_evaluations": RuleEvaluation,
        "review_tasks": ReviewTask,
        "messages": PatientMessage,
        "audit_events": AuditEvent,
    }
    return {
        name: db.scalar(select(func.count()).select_from(model)) or 0
        for name, model in models.items()
    }


def reset_demo_data(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Replace all mutable demo records with the known synthetic baseline."""

    deletion_order = [
        AuditEvent,
        PatientMessage,
        ContactAttempt,
        TaskEvidence,
        ReviewTask,
        RuleEvaluation,
        BloodPressureReading,
        ReadingSubmission,
        ClinicianProfile,
        PatientProfile,
        User,
    ]
    for model in deletion_order:
        db.execute(delete(model))
    db.flush()
    return seed_demo_data(db, now=now)
