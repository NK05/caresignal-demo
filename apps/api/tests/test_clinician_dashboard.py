from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import (
    BloodPressureReading,
    ReviewTask,
    RuleEvaluation,
    TaskEvidence,
    TaskPriority,
    TaskStatus,
)
from app.seed import CLINICIAN_IDS, PATIENT_IDS, USER_IDS, seed_demo_data

NOW = datetime.now(UTC).replace(microsecond=0)


def _add_dashboard_task(
    db: Session,
    *,
    key: int,
    patient_key: str,
    priority: TaskPriority,
    status: TaskStatus,
    assigned_clinician_id: str | None,
    acknowledged_at: datetime | None = None,
    due_at: datetime | None = None,
    resolved_at: datetime | None = None,
) -> ReviewTask:
    reading = db.scalar(
        select(BloodPressureReading)
        .where(BloodPressureReading.patient_id == PATIENT_IDS[patient_key])
        .order_by(BloodPressureReading.measured_at.desc())
    )
    assert reading is not None
    evaluation = RuleEvaluation(
        id=f"90000000-0000-4000-8000-{key:012d}",
        patient_id=reading.patient_id,
        reading_id=reading.id,
        rule_id=f"dashboard.test-rule-{key}",
        rule_version="dashboard-test-1",
        triggered=True,
        priority=priority,
        reason=f"Synthetic dashboard reason {key}.",
        evidence={
            "title": f"Dashboard marker {key}",
            "sla_minutes": 240,
            "synthetic": True,
        },
        source_reference="Test-only synthetic dashboard configuration",
        evaluated_at=NOW - timedelta(hours=key + 1),
    )
    db.add(evaluation)
    db.flush()
    task = ReviewTask(
        id=f"91000000-0000-4000-8000-{key:012d}",
        patient_id=reading.patient_id,
        priority=priority,
        status=status,
        assigned_clinician_id=assigned_clinician_id,
        primary_rule_evaluation_id=evaluation.id,
        opened_at=evaluation.evaluated_at,
        acknowledged_at=acknowledged_at,
        due_at=due_at,
        resolved_at=resolved_at,
        outcome_code="completed" if status is TaskStatus.RESOLVED else None,
    )
    db.add(task)
    db.flush()
    db.add(TaskEvidence(task_id=task.id, rule_evaluation_id=evaluation.id))
    return task


@pytest.fixture
def clinician_client(db_session: Session) -> Generator[TestClient, None, None]:
    seed_demo_data(db_session, now=NOW)
    _add_dashboard_task(
        db_session,
        key=1,
        patient_key="rudo",
        priority=TaskPriority.NEEDS_REVIEW,
        status=TaskStatus.ASSIGNED,
        assigned_clinician_id=CLINICIAN_IDS["doctor"],
        due_at=NOW + timedelta(hours=2),
    )
    _add_dashboard_task(
        db_session,
        key=2,
        patient_key="tawanda",
        priority=TaskPriority.WATCH,
        status=TaskStatus.IN_REVIEW,
        assigned_clinician_id=CLINICIAN_IDS["nurse"],
        acknowledged_at=NOW - timedelta(hours=1),
        due_at=NOW + timedelta(hours=4),
    )
    _add_dashboard_task(
        db_session,
        key=3,
        patient_key="tariro",
        priority=TaskPriority.ROUTINE,
        status=TaskStatus.RESOLVED,
        assigned_clinician_id=CLINICIAN_IDS["doctor"],
        acknowledged_at=NOW - timedelta(hours=2),
        due_at=NOW - timedelta(hours=1),
        resolved_at=NOW - timedelta(minutes=30),
    )
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


def test_clinician_dashboard_requires_clinician_role(clinician_client: TestClient) -> None:
    assert clinician_client.get("/api/v1/clinician/dashboard").status_code == 401
    assert (
        clinician_client.get(
            "/api/v1/clinician/dashboard",
            headers=_headers("tariro"),
        ).status_code
        == 403
    )
    assert (
        clinician_client.get(
            "/api/v1/clinician/dashboard",
            headers=_headers("nurse"),
        ).status_code
        == 200
    )


def test_dashboard_returns_summary_and_priority_then_age_order(
    clinician_client: TestClient,
) -> None:
    response = clinician_client.get(
        "/api/v1/clinician/dashboard",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["synthetic_data"] is True
    assert body["summary"] == {
        "unassigned": 1,
        "awaiting_acknowledgement": 1,
        "in_review": 1,
        "overdue": 1,
        "resolved_today": 1,
    }
    assert [task["priority"] for task in body["tasks"]] == [
        "urgent_review",
        "needs_review",
        "watch",
    ]
    urgent = body["tasks"][0]
    assert urgent["patient_synthetic_identifier"] == "CS-PAT-004"
    assert urgent["patient_display_name"] == "Nomsa Dube"
    assert urgent["preferred_language"] == "nd"
    assert urgent["latest_reading"]["systolic"] == 186
    assert urgent["latest_reading"]["diastolic"] == 122
    assert urgent["overdue"] is True
    assert urgent["assigned_owner"] is None
    assert urgent["flag_reason"]
    assert urgent["task_age_minutes"] >= 0
    assert {owner["clinician_id"] for owner in body["available_owners"]} == {
        CLINICIAN_IDS["doctor"],
        CLINICIAN_IDS["nurse"],
    }


@pytest.mark.parametrize(
    ("query", "expected_identifiers"),
    [
        ("priority=watch", ["CS-PAT-003"]),
        ("status=resolved", ["CS-PAT-001"]),
        (f"owner={CLINICIAN_IDS['doctor']}", ["CS-PAT-002"]),
        ("owner=unassigned", ["CS-PAT-004"]),
        ("overdue=true", ["CS-PAT-004"]),
        ("language=sn", ["CS-PAT-003"]),
        ("medication_adherence_signal=true", ["CS-PAT-003"]),
    ],
)
def test_task_queue_filters(
    clinician_client: TestClient,
    query: str,
    expected_identifiers: list[str],
) -> None:
    response = clinician_client.get(
        f"/api/v1/clinician/tasks?{query}",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(expected_identifiers)
    assert [task["patient_synthetic_identifier"] for task in body["tasks"]] == (
        expected_identifiers
    )


def test_task_queue_rejects_invalid_filter_values(clinician_client: TestClient) -> None:
    response = clinician_client.get(
        "/api/v1/clinician/tasks?priority=diagnosis&status=waiting",
        headers=_headers(),
    )

    assert response.status_code == 422
