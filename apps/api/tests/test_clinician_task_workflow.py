from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import AuditEvent, ReviewTask, TaskStatus
from app.seed import CLINICIAN_IDS, USER_IDS, seed_demo_data

NOW = datetime.now(UTC).replace(microsecond=0)
TASK_ID = "51000000-0000-4000-8000-000000000001"


@pytest.fixture
def task_client(db_session: Session) -> Generator[TestClient, None, None]:
    seed_demo_data(db_session, now=NOW)
    db_session.commit()

    def override_database() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_database
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def _headers(user_key: str = "doctor") -> dict[str, str]:
    return {"X-Demo-Session": USER_IDS[user_key]}


def _post(
    client: TestClient,
    action: str,
    *,
    user_key: str = "doctor",
    body: dict[str, object] | None = None,
):
    return client.post(
        f"/api/v1/clinician/tasks/{TASK_ID}/{action}",
        headers=_headers(user_key),
        json=body,
    )


def test_task_detail_requires_clinician_and_returns_confirmed_evidence(
    task_client: TestClient,
) -> None:
    assert task_client.get(f"/api/v1/clinician/tasks/{TASK_ID}").status_code == 401
    assert (
        task_client.get(
            f"/api/v1/clinician/tasks/{TASK_ID}",
            headers=_headers("nomsa"),
        ).status_code
        == 403
    )
    assert (
        task_client.get(
            "/api/v1/clinician/tasks/00000000-0000-4000-8000-000000000000",
            headers=_headers(),
        ).status_code
        == 404
    )

    response = task_client.get(
        f"/api/v1/clinician/tasks/{TASK_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["synthetic_data"] is True
    assert body["task"]["patient_synthetic_identifier"] == "CS-PAT-004"
    assert body["task"]["patient_display_name"] == "Nomsa Dube"
    assert body["task"]["status"] == "open"
    assert len(body["readings"]) == 1
    reading = body["readings"][0]
    assert reading["reading_id"] == "41000000-0000-4000-8000-000000000006"
    assert reading["systolic"] == 186
    assert reading["diastolic"] == 122
    assert reading["medication_taken"] == "yes"
    assert reading["missed_medication_reason_code"] is None
    assert reading["context_codes"] == []
    assert reading["note"] is None
    assert body["evidence"][0]["rule_id"] == "demo-single-reading-review"
    assert body["evidence"][0]["reason"].startswith("Illustrative demo rule")
    assert body["evidence"][0]["source_reference"].startswith(
        "Illustrative prototype configuration"
    )
    assert body["current_clinician"]["clinician_id"] == CLINICIAN_IDS["doctor"]
    assert body["allowed_actions"]["can_assign"] is True
    assert body["allowed_actions"]["can_resolve"] is False


def test_complete_owned_task_workflow_records_every_mutation(
    task_client: TestClient,
    db_session: Session,
) -> None:
    assigned = _post(
        task_client,
        "assign",
        body={"clinician_id": CLINICIAN_IDS["doctor"]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["task"]["status"] == "assigned"
    assert assigned.json()["task"]["unacknowledged"] is True

    wrong_owner = _post(task_client, "acknowledge", user_key="nurse")
    assert wrong_owner.status_code == 409
    assert wrong_owner.json()["detail"] == "Task action requires the assigned clinician"

    acknowledged = _post(task_client, "acknowledge")
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged_at"] is not None
    assert acknowledged.json()["allowed_actions"]["can_start_review"] is True

    reviewing = _post(task_client, "start-review")
    assert reviewing.status_code == 200
    assert reviewing.json()["task"]["status"] == "in_review"
    assert reviewing.json()["allowed_actions"]["can_resolve"] is True

    invalid_resolution = _post(task_client, "resolve", body={"outcome_code": "diagnosed"})
    assert invalid_resolution.status_code == 422

    resolved = _post(
        task_client,
        "resolve",
        body={
            "outcome_code": "follow_up_planned",
            "outcome_note": "Synthetic follow-up was arranged.",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["task"]["status"] == "resolved"
    assert resolved.json()["outcome_code"] == "follow_up_planned"
    assert resolved.json()["resolved_at"] is not None
    assert resolved.json()["allowed_actions"]["can_reopen"] is True

    missing_reason = _post(task_client, "reopen", body={"reason": "   "})
    assert missing_reason.status_code == 422

    reopened = _post(
        task_client,
        "reopen",
        body={"reason": "New synthetic evidence needs another review."},
    )
    assert reopened.status_code == 200
    assert reopened.json()["task"]["status"] == "in_review"
    assert reopened.json()["reopened_count"] == 1
    assert reopened.json()["outcome_code"] is None
    assert reopened.json()["resolved_at"] is None

    event_types = list(
        db_session.scalars(
            select(AuditEvent.event_type)
            .where(AuditEvent.entity_id == TASK_ID)
            .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        )
    )
    assert event_types == [
        "review_task.assigned",
        "review_task.acknowledged",
        "review_task.review_started",
        "review_task.resolved",
        "review_task.reopened",
    ]


def test_assignment_changes_reset_acknowledgement_and_unassignment_is_explicit(
    task_client: TestClient,
    db_session: Session,
) -> None:
    assert (
        _post(
            task_client,
            "assign",
            body={"clinician_id": CLINICIAN_IDS["nurse"]},
        ).status_code
        == 200
    )
    assert _post(task_client, "acknowledge", user_key="nurse").status_code == 200

    reassigned = _post(
        task_client,
        "assign",
        body={"clinician_id": CLINICIAN_IDS["doctor"]},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["acknowledged_at"] is None
    assert reassigned.json()["task"]["unacknowledged"] is True

    unassigned = _post(task_client, "assign", body={"clinician_id": None})
    assert unassigned.status_code == 200
    assert unassigned.json()["task"]["status"] == "open"
    assert unassigned.json()["task"]["assigned_owner"] is None

    task = db_session.get(ReviewTask, TASK_ID)
    assert task is not None
    assert task.status is TaskStatus.OPEN
    assert task.assigned_clinician_id is None
    assert task.acknowledged_at is None


def test_in_review_task_can_be_returned_to_another_reviewer(
    task_client: TestClient,
    db_session: Session,
) -> None:
    _post(
        task_client,
        "assign",
        body={"clinician_id": CLINICIAN_IDS["doctor"]},
    )
    _post(task_client, "acknowledge")
    _post(task_client, "start-review")

    returned = _post(
        task_client,
        "assign",
        body={"clinician_id": CLINICIAN_IDS["nurse"]},
    )

    assert returned.status_code == 200
    body = returned.json()
    assert body["task"]["status"] == "assigned"
    assert body["task"]["assigned_owner"]["clinician_id"] == CLINICIAN_IDS["nurse"]
    assert body["acknowledged_at"] is None
    assert body["task"]["unacknowledged"] is True
    task = db_session.get(ReviewTask, TASK_ID)
    assert task is not None
    assert task.status is TaskStatus.ASSIGNED
    assert task.assigned_clinician_id == CLINICIAN_IDS["nurse"]
    assert (
        db_session.scalar(
            select(AuditEvent.event_type).where(
                AuditEvent.entity_id == TASK_ID,
                AuditEvent.event_type == "review_task.returned_to_assigned",
            )
        )
        == "review_task.returned_to_assigned"
    )


def test_invalid_order_and_unknown_assignment_are_rejected_without_mutation(
    task_client: TestClient,
    db_session: Session,
) -> None:
    assert _post(task_client, "start-review").status_code == 409
    assert (
        _post(
            task_client,
            "assign",
            body={"clinician_id": "21000000-0000-4000-8000-999999999999"},
        ).status_code
        == 409
    )
    assert (
        _post(task_client, "resolve", body={"outcome_code": "review_completed"}).status_code == 409
    )

    task = db_session.get(ReviewTask, TASK_ID)
    assert task is not None
    assert task.status is TaskStatus.OPEN
    assert task.assigned_clinician_id is None
    assert list(db_session.scalars(select(AuditEvent).where(AuditEvent.entity_id == TASK_ID))) == []
