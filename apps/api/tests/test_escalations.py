from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import AuditEvent, PatientMessage
from app.seed import seed_demo_data


@pytest.fixture
def escalation_client(db_session: Session) -> Generator[TestClient, None, None]:
    seed_demo_data(db_session)
    db_session.commit()

    def override_database() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_database
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_escalation_endpoint_is_protected_idempotent_and_audited(
    escalation_client: TestClient, db_session: Session
) -> None:
    path = "/api/v1/system/escalations/run"
    assert escalation_client.post(path).status_code == 403
    headers = {"X-Demo-System-Token": get_settings().caresignal_demo_reset_token}
    messages_before = db_session.scalar(select(func.count()).select_from(PatientMessage)) or 0

    first = escalation_client.post(path, headers=headers)
    assert first.status_code == 200
    assert first.json()["overdue_active_tasks"] >= 1
    assert first.json()["newly_escalated_tasks"] >= 1

    event = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "review_task.overdue_escalated")
    )
    assert event is not None
    assert event.event_metadata["priority_unchanged"] is True
    assert event.event_metadata["automatic_patient_message"] is False

    second = escalation_client.post(path, headers=headers)
    assert second.status_code == 200
    assert second.json()["newly_escalated_tasks"] == 0
    messages_after = db_session.scalar(select(func.count()).select_from(PatientMessage)) or 0
    assert messages_after == messages_before
