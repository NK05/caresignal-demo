from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import (
    AuditEvent,
    BloodPressureReading,
    ReadingSubmission,
    ReviewTask,
    RuleEvaluation,
    SubmissionStatus,
    TaskEvidence,
    TaskPriority,
)
from app.rules.config import RULESET_VERSION
from app.seed import PATIENT_IDS, USER_IDS, seed_demo_data


@pytest.fixture
def patient_client(db_session: Session) -> Generator[TestClient, None, None]:
    seed_demo_data(db_session, now=datetime(2026, 7, 17, 12, tzinfo=UTC))
    db_session.commit()

    def override_database() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_database
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def _headers(user_key: str) -> dict[str, str]:
    return {"X-Demo-Session": USER_IDS[user_key]}


def _candidate(**overrides: object) -> dict[str, object]:
    candidate: dict[str, object] = {
        "systolic": 132,
        "diastolic": 84,
        "measured_at": "2026-07-17T10:30:00+02:00",
        "medication_taken": "yes",
        "context_codes": ["rested"],
        "note": "Synthetic structured-form note.",
    }
    candidate.update(overrides)
    return candidate


def _submit(client: TestClient, *, user_key: str = "tariro") -> dict[str, object]:
    response = client.post(
        "/api/v1/patient/submissions/structured",
        headers=_headers(user_key),
        json=_candidate(),
    )
    assert response.status_code == 201
    return response.json()


def test_demo_session_selects_only_active_seeded_personas(
    patient_client: TestClient,
) -> None:
    response = patient_client.post(
        "/api/v1/demo/session",
        json={"user_id": USER_IDS["tariro"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "session_token": USER_IDS["tariro"],
        "user_id": USER_IDS["tariro"],
        "display_name": "Tariro Moyo",
        "role": "patient",
        "preferred_language": "en",
        "synthetic_data": True,
        "non_production_auth": True,
    }
    assert (
        patient_client.post(
            "/api/v1/demo/session",
            json={"user_id": "99999999-0000-4000-8000-000000000001"},
        ).status_code
        == 404
    )


def test_patient_routes_require_a_patient_demo_session(patient_client: TestClient) -> None:
    assert (
        patient_client.post(
            "/api/v1/patient/submissions/structured",
            json=_candidate(),
        ).status_code
        == 401
    )
    assert (
        patient_client.post(
            "/api/v1/patient/submissions/structured",
            headers=_headers("doctor"),
            json=_candidate(),
        ).status_code
        == 403
    )


def test_submission_requires_confirmation_before_creating_reading(
    patient_client: TestClient,
    db_session: Session,
) -> None:
    readings_before = db_session.scalar(select(func.count()).select_from(BloodPressureReading))
    evaluations_before = db_session.scalar(select(func.count()).select_from(RuleEvaluation))
    tasks_before = db_session.scalar(select(func.count()).select_from(ReviewTask))

    submission_body = _submit(patient_client)
    submission_id = str(submission_body["id"])

    assert submission_body["status"] == "pending_confirmation"
    assert submission_body["candidate_payload"]["requires_confirmation"] is True
    assert (
        db_session.scalar(
            select(BloodPressureReading).where(BloodPressureReading.submission_id == submission_id)
        )
        is None
    )
    assert db_session.scalar(select(func.count()).select_from(BloodPressureReading)) == (
        readings_before
    )
    assert db_session.scalar(select(func.count()).select_from(ReviewTask)) == tasks_before
    assert db_session.scalar(select(func.count()).select_from(RuleEvaluation)) == evaluations_before

    response = patient_client.post(
        f"/api/v1/patient/submissions/{submission_id}/confirm",
        headers=_headers("tariro"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["submission"]["status"] == "confirmed"
    assert body["reading"]["submission_id"] == submission_id
    assert body["reading"]["systolic"] == 132
    assert body["rules_evaluated"] is True
    assert body["evaluation_count"] == 6
    assert body["care_team_notified"] is False
    assert body["acknowledgement"] == "Reading confirmed."
    assert "diagnos" not in body["acknowledgement"].lower()
    assert db_session.scalar(select(func.count()).select_from(BloodPressureReading)) == (
        readings_before + 1
    )
    assert db_session.scalar(select(func.count()).select_from(ReviewTask)) == tasks_before
    assert db_session.scalar(select(func.count()).select_from(RuleEvaluation)) == (
        evaluations_before + 6
    )
    persisted_evaluations = db_session.scalars(
        select(RuleEvaluation).where(RuleEvaluation.reading_id == body["reading"]["id"])
    ).all()
    assert len(persisted_evaluations) == 6
    assert all(evaluation.rule_version == RULESET_VERSION for evaluation in persisted_evaluations)
    assert not any(evaluation.triggered for evaluation in persisted_evaluations)
    assert all(
        evaluation.evidence["illustrative_not_clinically_validated"] is True
        for evaluation in persisted_evaluations
    )

    repeat = patient_client.post(
        f"/api/v1/patient/submissions/{submission_id}/confirm",
        headers=_headers("tariro"),
    )
    assert repeat.status_code == 200
    assert repeat.json()["reading"]["id"] == body["reading"]["id"]
    assert db_session.scalar(select(func.count()).select_from(BloodPressureReading)) == (
        readings_before + 1
    )
    assert db_session.scalar(select(func.count()).select_from(RuleEvaluation)) == (
        evaluations_before + 6
    )
    confirmed_audits = db_session.scalars(
        select(AuditEvent).where(
            AuditEvent.entity_id == submission_id,
            AuditEvent.event_type == "blood_pressure_reading.confirmed",
        )
    ).all()
    assert len(confirmed_audits) == 1


def test_patient_cannot_access_or_confirm_another_patients_submission(
    patient_client: TestClient,
) -> None:
    submission_id = str(_submit(patient_client)["id"])

    assert (
        patient_client.get(
            f"/api/v1/patient/submissions/{submission_id}",
            headers=_headers("rudo"),
        ).status_code
        == 404
    )
    assert (
        patient_client.post(
            f"/api/v1/patient/submissions/{submission_id}/confirm",
            headers=_headers("rudo"),
        ).status_code
        == 404
    )

    rudo_readings = patient_client.get(
        "/api/v1/patient/readings",
        headers=_headers("rudo"),
    )
    assert rudo_readings.status_code == 200
    assert rudo_readings.json()
    assert all(reading["patient_id"] == PATIENT_IDS["rudo"] for reading in rudo_readings.json())


@pytest.mark.parametrize(
    "candidate",
    [
        _candidate(systolic=39),
        _candidate(systolic=120.5),
        _candidate(context_codes=["unsupported_context"]),
        _candidate(measured_at="2026-07-17T10:30:00"),
        _candidate(medication_taken="unknown"),
        _candidate(missed_medication_reason_code="forgot"),
        {**_candidate(), "unexpected_field": "rejected"},
    ],
)
def test_structured_submission_rejects_invalid_or_ambiguous_candidates(
    patient_client: TestClient,
    candidate: dict[str, object],
) -> None:
    response = patient_client.post(
        "/api/v1/patient/submissions/structured",
        headers=_headers("tariro"),
        json=candidate,
    )

    assert response.status_code == 422


def test_correction_and_rejection_retain_no_unconfirmed_clinical_values(
    patient_client: TestClient,
    db_session: Session,
) -> None:
    original_id = str(_submit(patient_client)["id"])
    correction = patient_client.post(
        f"/api/v1/patient/submissions/{original_id}/correct",
        headers=_headers("tariro"),
        json=_candidate(systolic=134, diastolic=86),
    )

    assert correction.status_code == 201
    revised_id = correction.json()["revised_submission"]["id"]
    original = db_session.get(ReadingSubmission, original_id)
    assert original is not None
    assert original.status is SubmissionStatus.CORRECTED
    assert original.candidate_payload == {}
    assert (
        db_session.scalar(
            select(BloodPressureReading).where(
                BloodPressureReading.submission_id.in_([original_id, revised_id])
            )
        )
        is None
    )

    rejection = patient_client.post(
        f"/api/v1/patient/submissions/{revised_id}/reject",
        headers=_headers("tariro"),
    )
    assert rejection.status_code == 200
    assert rejection.json()["status"] == "rejected"
    revised = db_session.get(ReadingSubmission, revised_id)
    assert revised is not None
    assert revised.candidate_payload == {}
    assert (
        patient_client.post(
            f"/api/v1/patient/submissions/{revised_id}/confirm",
            headers=_headers("tariro"),
        ).status_code
        == 409
    )


def test_confirmation_revalidates_stored_candidate_atomically(
    patient_client: TestClient,
    db_session: Session,
) -> None:
    submission_id = str(_submit(patient_client)["id"])
    submission = db_session.get(ReadingSubmission, submission_id)
    assert submission is not None
    submission.candidate_payload = {
        **submission.candidate_payload,
        "systolic": 999,
    }
    db_session.commit()

    response = patient_client.post(
        f"/api/v1/patient/submissions/{submission_id}/confirm",
        headers=_headers("tariro"),
    )

    assert response.status_code == 409
    db_session.refresh(submission)
    assert submission.status is SubmissionStatus.PENDING_CONFIRMATION
    assert (
        db_session.scalar(
            select(BloodPressureReading).where(BloodPressureReading.submission_id == submission_id)
        )
        is None
    )


def test_confirmation_rolls_back_reading_when_rule_evaluation_fails(
    patient_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.readings as reading_service

    submission_id = str(_submit(patient_client)["id"])
    evaluations_before = db_session.scalar(select(func.count()).select_from(RuleEvaluation))

    def fail_evaluation(*_args: object, **_kwargs: object) -> list[RuleEvaluation]:
        raise RuntimeError("forced rule evaluation failure")

    monkeypatch.setattr(reading_service, "evaluate_confirmed_reading", fail_evaluation)

    with pytest.raises(RuntimeError, match="forced rule evaluation failure"):
        patient_client.post(
            f"/api/v1/patient/submissions/{submission_id}/confirm",
            headers=_headers("tariro"),
        )

    submission = db_session.get(ReadingSubmission, submission_id)
    assert submission is not None
    assert submission.status is SubmissionStatus.PENDING_CONFIRMATION
    assert (
        db_session.scalar(
            select(BloodPressureReading).where(BloodPressureReading.submission_id == submission_id)
        )
        is None
    )
    assert db_session.scalar(select(func.count()).select_from(RuleEvaluation)) == evaluations_before


def test_triggered_evaluation_creates_one_task_and_later_evidence_reuses_it(
    patient_client: TestClient,
    db_session: Session,
) -> None:
    tasks_before = db_session.scalar(select(func.count()).select_from(ReviewTask))

    first_submission = patient_client.post(
        "/api/v1/patient/submissions/structured",
        headers=_headers("tawanda"),
        json=_candidate(
            systolic=132,
            diastolic=84,
            medication_taken="no",
            missed_medication_reason_code="refill_unavailable",
        ),
    )
    assert first_submission.status_code == 201
    first_id = first_submission.json()["id"]
    assert db_session.scalar(select(func.count()).select_from(ReviewTask)) == tasks_before

    first_confirmation = patient_client.post(
        f"/api/v1/patient/submissions/{first_id}/confirm",
        headers=_headers("tawanda"),
    )
    assert first_confirmation.status_code == 200
    assert first_confirmation.json()["care_team_notified"] is True
    assert first_confirmation.json()["acknowledgement"] == (
        "Reading confirmed. Your care team has been notified for review."
    )

    tasks = db_session.scalars(
        select(ReviewTask).where(ReviewTask.patient_id == PATIENT_IDS["tawanda"])
    ).all()
    assert len(tasks) == 1
    task = tasks[0]
    assert task.priority is TaskPriority.NEEDS_REVIEW
    assert task.due_at is not None
    assert db_session.scalar(select(func.count()).select_from(ReviewTask)) == tasks_before + 1

    second_submission = patient_client.post(
        "/api/v1/patient/submissions/structured",
        headers=_headers("tawanda"),
        json=_candidate(
            systolic=132,
            diastolic=84,
            measured_at="2026-07-17T11:30:00+02:00",
            medication_taken="no",
            missed_medication_reason_code="forgot",
        ),
    )
    assert second_submission.status_code == 201
    second_id = second_submission.json()["id"]
    second_confirmation = patient_client.post(
        f"/api/v1/patient/submissions/{second_id}/confirm",
        headers=_headers("tawanda"),
    )

    assert second_confirmation.status_code == 200
    assert second_confirmation.json()["care_team_notified"] is True
    assert db_session.scalar(select(func.count()).select_from(ReviewTask)) == tasks_before + 1
    evidence_links = db_session.scalars(
        select(TaskEvidence).where(TaskEvidence.task_id == task.id)
    ).all()
    assert len(evidence_links) == 2
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.entity_id == task.id,
                AuditEvent.event_type == "review_task.created",
            )
        )
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.entity_id == task.id,
                AuditEvent.event_type == "review_task.evidence_added",
            )
        )
        == 1
    )


def test_confirmation_rolls_back_when_task_synchronization_fails(
    patient_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.readings as reading_service

    submission = patient_client.post(
        "/api/v1/patient/submissions/structured",
        headers=_headers("tawanda"),
        json=_candidate(
            medication_taken="no",
            missed_medication_reason_code="forgot",
        ),
    )
    assert submission.status_code == 201
    submission_id = submission.json()["id"]
    readings_before = db_session.scalar(select(func.count()).select_from(BloodPressureReading))
    evaluations_before = db_session.scalar(select(func.count()).select_from(RuleEvaluation))
    tasks_before = db_session.scalar(select(func.count()).select_from(ReviewTask))

    def fail_task_sync(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("forced task synchronization failure")

    monkeypatch.setattr(reading_service, "sync_review_tasks", fail_task_sync)

    with pytest.raises(RuntimeError, match="forced task synchronization failure"):
        patient_client.post(
            f"/api/v1/patient/submissions/{submission_id}/confirm",
            headers=_headers("tawanda"),
        )

    stored_submission = db_session.get(ReadingSubmission, submission_id)
    assert stored_submission is not None
    assert stored_submission.status is SubmissionStatus.PENDING_CONFIRMATION
    assert db_session.scalar(select(func.count()).select_from(BloodPressureReading)) == (
        readings_before
    )
    assert db_session.scalar(select(func.count()).select_from(RuleEvaluation)) == evaluations_before
    assert db_session.scalar(select(func.count()).select_from(ReviewTask)) == tasks_before
