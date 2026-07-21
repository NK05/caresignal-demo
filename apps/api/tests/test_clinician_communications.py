from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import AuditEvent, Channel, ContactAttempt, PatientMessage, PatientProfile
from app.seed import CLINICIAN_IDS, PATIENT_IDS, USER_IDS, seed_demo_data
from app.services.whatsapp import get_whatsapp_gateway

NOW = datetime.now(UTC).replace(microsecond=0)
TASK_ID = "51000000-0000-4000-8000-000000000001"


@pytest.fixture
def communication_client(db_session: Session) -> Generator[TestClient, None, None]:
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


def _headers(user: str = "doctor") -> dict[str, str]:
    return {"X-Demo-Session": USER_IDS[user]}


def _post(client: TestClient, action: str, body: dict | None = None, user: str = "doctor"):
    return client.post(
        f"/api/v1/clinician/tasks/{TASK_ID}/{action}",
        headers=_headers(user),
        json=body,
    )


def _start_review(client: TestClient) -> None:
    assert (
        _post(
            client,
            "assign",
            {"clinician_id": CLINICIAN_IDS["doctor"]},
        ).status_code
        == 200
    )
    assert _post(client, "acknowledge").status_code == 200
    assert _post(client, "start-review").status_code == 200


def test_contact_attempt_requires_owned_review_and_appears_in_timeline(
    communication_client: TestClient,
    db_session: Session,
) -> None:
    request = {
        "channel": "whatsapp_simulator",
        "outcome_code": "message_left",
        "note": "Synthetic contact note.",
    }
    assert _post(communication_client, "contact-attempts", request).status_code == 409
    _start_review(communication_client)
    assert (
        _post(
            communication_client,
            "contact-attempts",
            request,
            user="nurse",
        ).status_code
        == 409
    )

    response = _post(communication_client, "contact-attempts", request)

    assert response.status_code == 200
    body = response.json()
    assert body["contact_attempts"][0]["outcome_code"] == "message_left"
    assert body["contact_attempts"][0]["note"] == "Synthetic contact note."
    assert body["contact_attempts"][0]["clinician"]["display_name"] == "Dr Chipo Moyo"
    assert body["audit_events"][0]["event_type"] == "review_task.contact_recorded"
    assert db_session.scalar(select(ContactAttempt.id)) is not None


def test_clinician_message_must_be_approved_before_simulated_send(
    communication_client: TestClient,
    db_session: Session,
) -> None:
    _start_review(communication_client)
    draft_response = _post(
        communication_client,
        "draft-message",
        {
            "language": "nd",
            "content": "Sicela ubuye eklinikhi ukuze iqembu lakho likunakekele.",
        },
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()["messages"][0]
    assert draft["generation_type"] == "clinician_authored"
    assert draft["approval_status"] == "draft"
    assert draft["delivery_status"] == "not_sent"

    premature_send = _post(
        communication_client,
        "approve-message",
        {"message_id": draft["message_id"], "send": True},
    )
    assert premature_send.status_code == 409
    assert premature_send.json()["detail"] == "Message must be approved before it can be sent"

    wrong_owner = _post(
        communication_client,
        "approve-message",
        {"message_id": draft["message_id"], "send": False},
        user="nurse",
    )
    assert wrong_owner.status_code == 409

    approved_response = _post(
        communication_client,
        "approve-message",
        {"message_id": draft["message_id"], "send": False},
    )
    approved = approved_response.json()["messages"][0]
    assert approved["approval_status"] == "approved"
    assert approved["approved_by"] == USER_IDS["doctor"]
    assert approved["approved_at"] is not None
    assert approved["sent_at"] is None

    sent_response = _post(
        communication_client,
        "approve-message",
        {"message_id": draft["message_id"], "send": True},
    )
    sent = sent_response.json()["messages"][0]
    assert sent["approval_status"] == "sent"
    assert sent["delivery_status"] == "sent"
    assert sent["sent_at"] is not None

    stored = db_session.get(PatientMessage, draft["message_id"])
    assert stored is not None and stored.content == draft["content"]
    message_events = list(
        db_session.scalars(
            select(AuditEvent.event_type).where(
                AuditEvent.entity_id == TASK_ID,
                AuditEvent.event_type.in_(
                    {
                        "review_task.message_drafted",
                        "review_task.message_approved",
                        "review_task.message_sent",
                    }
                ),
            )
        )
    )
    assert set(message_events) == {
        "review_task.message_drafted",
        "review_task.message_approved",
        "review_task.message_sent",
    }


def test_message_contract_rejects_ai_claims_and_actions_after_resolution(
    communication_client: TestClient,
) -> None:
    _start_review(communication_client)
    invalid = _post(
        communication_client,
        "draft-message",
        {
            "language": "en",
            "content": "Synthetic draft.",
            "generation_type": "ai_draft",
        },
    )
    assert invalid.status_code == 422

    assert (
        _post(
            communication_client,
            "resolve",
            {"outcome_code": "review_completed", "outcome_note": None},
        ).status_code
        == 200
    )
    assert (
        _post(
            communication_client,
            "draft-message",
            {"language": "en", "content": "Too late."},
        ).status_code
        == 409
    )
    assert (
        _post(
            communication_client,
            "contact-attempts",
            {"channel": "app", "outcome_code": "reached", "note": None},
        ).status_code
        == 409
    )


def test_approved_whatsapp_sandbox_message_uses_real_gateway_when_configured(
    communication_client: TestClient,
    db_session: Session,
) -> None:
    class RecordingGateway:
        configured = True
        webhook_configured = True

        def __init__(self) -> None:
            self.sent: list[tuple[str, str]] = []

        def destination_for_patient(self, patient: PatientProfile) -> str | None:
            return "263771234567" if patient.id == PATIENT_IDS["nomsa"] else None

        def send_text(self, *, destination: str, content: str) -> str:
            self.sent.append((destination, content))
            return "wamid.clinician-approved.011"

    gateway = RecordingGateway()
    app.dependency_overrides[get_whatsapp_gateway] = lambda: gateway
    patient = db_session.get(PatientProfile, PATIENT_IDS["nomsa"])
    assert patient is not None
    patient.preferred_channel = Channel.WHATSAPP_SANDBOX
    db_session.commit()
    _start_review(communication_client)

    draft_response = _post(
        communication_client,
        "draft-message",
        {"language": "en", "content": "Synthetic clinician-approved follow-up."},
    )
    draft = draft_response.json()["messages"][0]
    _post(
        communication_client,
        "approve-message",
        {"message_id": draft["message_id"], "send": False},
    )
    sent_response = _post(
        communication_client,
        "approve-message",
        {"message_id": draft["message_id"], "send": True},
    )

    sent = sent_response.json()["messages"][0]
    assert sent["channel"] == "whatsapp_sandbox"
    assert sent["approval_status"] == "sent"
    assert sent["delivery_status"] == "sent"
    assert gateway.sent == [("263771234567", "Synthetic clinician-approved follow-up.")]
    stored = db_session.get(PatientMessage, draft["message_id"])
    assert stored is not None
    assert stored.provider_message_id == "wamid.clinician-approved.011"
    event = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "review_task.message_sent")
        .order_by(AuditEvent.created_at.desc())
    )
    assert event is not None
    assert event.event_metadata["simulated_delivery"] is False
