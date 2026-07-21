from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content import patient_text
from app.database import get_db
from app.main import app
from app.models import (
    BloodPressureReading,
    DeliveryStatus,
    Language,
    PatientMessage,
    ReadingSubmission,
    ReviewTask,
)
from app.schemas import ReadingExtraction
from app.seed import USER_IDS, seed_demo_data
from app.services.ai_extraction import ProviderExtraction, get_extraction_provider
from app.services.whatsapp import get_whatsapp_gateway

NOW = datetime(2026, 7, 18, 10, tzinfo=UTC)


class FakeProvider:
    def __init__(self) -> None:
        self.extraction = ReadingExtraction(
            language=Language.NDEBELE,
            systolic=170,
            diastolic=108,
            measurement_time_text="2026-07-18T11:30:00+02:00",
            medication_taken="yes",
            missed_medication_reason=None,
            context_codes=["rested"],
            unstructured_note=None,
            missing_fields=[],
            ambiguities=[],
            requires_confirmation=True,
        )

    def extract(self, **_kwargs: object) -> ProviderExtraction:
        return ProviderExtraction(
            extraction=self.extraction,
            request_id="resp_cs011_synthetic",
        )


class FakeGateway:
    configured = False
    webhook_configured = False

    def verify_token(self, _supplied_token: str) -> bool:
        return False

    def verify_signature(self, _body: bytes, _signature: str | None) -> bool:
        return False

    def patient_for_sender(self, _db: Session, _sender: str):  # noqa: ANN201
        return None

    def destination_for_patient(self, _patient):  # noqa: ANN001, ANN201
        return None

    def send_text(self, *, destination: str, content: str) -> str:
        raise AssertionError(f"Unexpected delivery to {destination}: {content}")


@pytest.fixture
def conversation_client(
    db_session: Session,
) -> Generator[tuple[TestClient, FakeProvider, FakeGateway], None, None]:
    seed_demo_data(db_session, now=NOW)
    db_session.commit()
    provider = FakeProvider()
    gateway = FakeGateway()

    def override_database() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_database
    app.dependency_overrides[get_extraction_provider] = lambda: provider
    app.dependency_overrides[get_whatsapp_gateway] = lambda: gateway
    client = TestClient(app)
    try:
        yield client, provider, gateway
    finally:
        app.dependency_overrides.clear()


def _headers(user: str = "rudo") -> dict[str, str]:
    return {"X-Demo-Session": USER_IDS[user]}


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_simulator_message_creates_history_and_pending_confirmation_only(
    conversation_client: tuple[TestClient, FakeProvider, FakeGateway],
    db_session: Session,
) -> None:
    client, _provider, gateway = conversation_client
    # A configured Meta adapter must not make the browser-based channel claim to be live WhatsApp.
    gateway.configured = True
    initial = {
        "submissions": _count(db_session, ReadingSubmission),
        "readings": _count(db_session, BloodPressureReading),
        "tasks": _count(db_session, ReviewTask),
    }

    response = client.post(
        "/api/v1/patient/conversation/messages",
        headers=_headers(),
        json={
            "message": (
                "I-BP yami ngu-170 over 108 ngo-11:30. Ngiwathathile amaphilisi, bengiphumule."
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation"]["channel_label"] == "WhatsApp-compatible simulator"
    assert body["conversation"]["real_whatsapp_configured"] is False
    assert [item["message_type"] for item in body["conversation"]["messages"]] == [
        "patient",
        "system",
    ]
    assert body["extraction"]["status"] == "ready_for_confirmation"
    assert body["conversation"]["pending_submission"]["status"] == "pending_confirmation"
    assert _count(db_session, ReadingSubmission) == initial["submissions"] + 1
    assert _count(db_session, BloodPressureReading) == initial["readings"]
    assert _count(db_session, ReviewTask) == initial["tasks"]
    assert _count(db_session, PatientMessage) == 2

    care_messages = client.get("/api/v1/patient/messages", headers=_headers())
    assert care_messages.status_code == 200
    assert care_messages.json() == []


def test_simulator_confirmation_runs_rules_only_after_explicit_action(
    conversation_client: tuple[TestClient, FakeProvider, FakeGateway],
    db_session: Session,
) -> None:
    client, _provider, _gateway = conversation_client
    sent = client.post(
        "/api/v1/patient/conversation/messages",
        headers=_headers(),
        json={"message": "I-BP yami ngu-170 over 108 ngo-11:30. Ngiwathathile amaphilisi."},
    ).json()
    submission_id = sent["conversation"]["pending_submission"]["id"]
    readings_before = _count(db_session, BloodPressureReading)

    response = client.post(
        f"/api/v1/patient/conversation/submissions/{submission_id}/confirm",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["care_team_notified"] is True
    assert body["acknowledgement"] == patient_text(Language.NDEBELE, "confirmed_notified")
    assert body["conversation"]["pending_submission"] is None
    assert body["conversation"]["messages"][-2]["content"] == patient_text(
        Language.NDEBELE, "confirm_command"
    )
    assert body["conversation"]["messages"][-1]["message_type"] == "system"
    assert _count(db_session, BloodPressureReading) == readings_before + 1


def test_text_confirmation_is_handled_deterministically_without_reextracting(
    conversation_client: tuple[TestClient, FakeProvider, FakeGateway],
    db_session: Session,
) -> None:
    client, provider, _gateway = conversation_client
    call_count = 0
    original_extract = provider.extract

    def counted_extract(**kwargs: object) -> ProviderExtraction:
        nonlocal call_count
        call_count += 1
        return original_extract(**kwargs)

    provider.extract = counted_extract  # type: ignore[method-assign]
    client.post(
        "/api/v1/patient/conversation/messages",
        headers=_headers(),
        json={"message": "Synthetic BP 170 over 108 at 11:30, medication taken."},
    )
    readings_before = _count(db_session, BloodPressureReading)

    response = client.post(
        "/api/v1/patient/conversation/messages",
        headers=_headers(),
        json={"message": "CONFIRM"},
    )

    assert response.status_code == 200
    assert response.json()["extraction"] is None
    assert response.json()["conversation"]["pending_submission"] is None
    assert response.json()["conversation"]["messages"][-1]["content"] == patient_text(
        Language.NDEBELE, "confirmed_notified"
    )
    assert call_count == 1
    assert _count(db_session, BloodPressureReading) == readings_before + 1


@pytest.mark.parametrize(
    ("user", "command", "language", "response_key"),
    [
        ("rudo", "Qinisekisa ukubalwa", Language.NDEBELE, "confirmed_notified"),
        ("tawanda", "Simbisa kuverengwa", Language.SHONA, "confirmed"),
    ],
)
def test_localized_confirmation_commands_use_localized_fixed_response(
    conversation_client: tuple[TestClient, FakeProvider, FakeGateway],
    user: str,
    command: str,
    language: Language,
    response_key: str,
) -> None:
    client, _provider, _gateway = conversation_client
    client.post(
        "/api/v1/patient/conversation/messages",
        headers=_headers(user),
        json={"message": "Synthetic complete BP message."},
    )

    response = client.post(
        "/api/v1/patient/conversation/messages",
        headers=_headers(user),
        json={"message": command},
    )

    assert response.status_code == 200
    assert response.json()["conversation"]["messages"][-1]["content"] == patient_text(
        language, response_key
    )


def test_simulator_cancellation_erases_unconfirmed_values(
    conversation_client: tuple[TestClient, FakeProvider, FakeGateway],
    db_session: Session,
) -> None:
    client, _provider, _gateway = conversation_client
    sent = client.post(
        "/api/v1/patient/conversation/messages",
        headers=_headers(),
        json={"message": "Synthetic BP 170 over 108 at 11:30, medication taken."},
    ).json()
    submission_id = sent["conversation"]["pending_submission"]["id"]
    readings_before = _count(db_session, BloodPressureReading)

    response = client.post(
        f"/api/v1/patient/conversation/submissions/{submission_id}/cancel",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["conversation"]["pending_submission"] is None
    submission = db_session.get(ReadingSubmission, submission_id)
    assert submission is not None
    assert submission.original_message is None
    assert submission.candidate_payload == {}
    assert _count(db_session, BloodPressureReading) == readings_before


def test_conversation_requires_patient_role_and_is_patient_isolated(
    conversation_client: tuple[TestClient, FakeProvider, FakeGateway],
) -> None:
    client, _provider, _gateway = conversation_client
    assert client.get("/api/v1/patient/conversation").status_code == 401
    assert client.get("/api/v1/patient/conversation", headers=_headers("doctor")).status_code == 403

    client.post(
        "/api/v1/patient/conversation/messages",
        headers=_headers(),
        json={"message": "Synthetic Ndebele message."},
    )
    other = client.get("/api/v1/patient/conversation", headers=_headers("tawanda"))
    assert other.status_code == 200
    assert other.json()["messages"] == []
    assert other.json()["pending_submission"] is None


def test_delivery_state_is_projected_in_conversation_history(
    conversation_client: tuple[TestClient, FakeProvider, FakeGateway],
    db_session: Session,
) -> None:
    client, _provider, _gateway = conversation_client
    message = PatientMessage(
        patient_id="11000000-0000-4000-8000-000000000002",
        direction="outbound",
        channel="whatsapp_simulator",
        language="nd",
        content="Synthetic care-team message.",
        generation_type="clinician_authored",
        approval_status="sent",
        delivery_status=DeliveryStatus.DELIVERED,
        task_id="51000000-0000-4000-8000-000000000001",
        sent_at=NOW,
    )
    db_session.add(message)
    db_session.commit()

    response = client.get("/api/v1/patient/conversation", headers=_headers())

    assert response.status_code == 200
    projected = response.json()["messages"][0]
    assert projected["message_type"] == "care_team"
    assert projected["delivery_status"] == "delivered"
