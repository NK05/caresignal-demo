from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import ReviewTask
from app.seed import CLINICIAN_IDS, PATIENT_IDS, USER_IDS, seed_demo_data


@pytest.fixture
def journey_client(db_session: Session) -> Generator[TestClient, None, None]:
    seed_demo_data(db_session, now=datetime.now(UTC))
    db_session.commit()

    def override_database() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_database
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def _headers(user: str) -> dict[str, str]:
    return {"X-Demo-Session": USER_IDS[user]}


def test_complete_english_patient_clinician_patient_loop(
    journey_client: TestClient,
    db_session: Session,
) -> None:
    patient_headers = _headers("tariro")
    clinician_headers = _headers("doctor")
    submission = journey_client.post(
        "/api/v1/patient/submissions/structured",
        headers=patient_headers,
        json={
            "systolic": 186,
            "diastolic": 122,
            "measured_at": datetime.now(UTC).isoformat(),
            "medication_taken": "yes",
            "context_codes": ["rested"],
            "note": "Synthetic English end-to-end reading.",
        },
    )
    assert submission.status_code == 201
    assert (
        db_session.scalar(select(ReviewTask).where(ReviewTask.patient_id == PATIENT_IDS["tariro"]))
        is None
    )

    confirmed = journey_client.post(
        f"/api/v1/patient/submissions/{submission.json()['id']}/confirm",
        headers=patient_headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["care_team_notified"] is True
    assert confirmed.json()["acknowledgement"] == (
        "Reading confirmed. Your care team has been notified for review."
    )
    task = db_session.scalar(
        select(ReviewTask).where(ReviewTask.patient_id == PATIENT_IDS["tariro"])
    )
    assert task is not None
    task_base = f"/api/v1/clinician/tasks/{task.id}"

    assert (
        journey_client.post(
            f"{task_base}/assign",
            headers=clinician_headers,
            json={"clinician_id": CLINICIAN_IDS["doctor"]},
        ).status_code
        == 200
    )
    assert (
        journey_client.post(f"{task_base}/acknowledge", headers=clinician_headers).status_code
        == 200
    )
    assert (
        journey_client.post(f"{task_base}/start-review", headers=clinician_headers).status_code
        == 200
    )

    draft = journey_client.post(
        f"{task_base}/draft-message",
        headers=clinician_headers,
        json={
            "language": "en",
            "content": "Please return to the clinic for a follow-up review with your care team.",
        },
    )
    message_id = draft.json()["messages"][0]["message_id"]
    assert journey_client.get("/api/v1/patient/messages", headers=patient_headers).json() == []

    assert (
        journey_client.post(
            f"{task_base}/approve-message",
            headers=clinician_headers,
            json={"message_id": message_id, "send": False},
        ).status_code
        == 200
    )
    assert journey_client.get("/api/v1/patient/messages", headers=patient_headers).json() == []

    assert (
        journey_client.post(
            f"{task_base}/approve-message",
            headers=clinician_headers,
            json={"message_id": message_id, "send": True},
        ).status_code
        == 200
    )
    assert (
        journey_client.post(
            f"{task_base}/resolve",
            headers=clinician_headers,
            json={"outcome_code": "follow_up_planned", "outcome_note": None},
        ).status_code
        == 200
    )

    follow_up = journey_client.get("/api/v1/patient/follow-up", headers=patient_headers)
    assert follow_up.status_code == 200
    assert follow_up.json()["status"] == "review_completed"
    assert "priority" not in follow_up.text.lower()
    assert "rule" not in follow_up.text.lower()
    assert follow_up.json()["latest_care_message"]["content"].startswith("Please return")
    messages = journey_client.get("/api/v1/patient/messages", headers=patient_headers).json()
    assert len(messages) == 1
    assert messages[0]["content"] == follow_up.json()["latest_care_message"]["content"]
    assert journey_client.get("/api/v1/patient/messages", headers=_headers("rudo")).json() == []
