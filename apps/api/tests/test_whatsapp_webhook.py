import hashlib
import hmac
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content import patient_text
from app.database import get_db
from app.main import app
from app.models import DeliveryStatus, Language, PatientMessage, PatientProfile
from app.schemas import ReadingExtraction
from app.seed import PATIENT_IDS, seed_demo_data
from app.services.ai_extraction import ProviderExtraction, get_extraction_provider
from app.services.whatsapp import MetaWhatsAppGateway, get_whatsapp_gateway

NOW = datetime(2026, 7, 18, 10, tzinfo=UTC)
SENDER = "263771234567"


class FakeProvider:
    def extract(self, **_kwargs: object) -> ProviderExtraction:
        return ProviderExtraction(
            extraction=ReadingExtraction(
                language=Language.NDEBELE,
                systolic=168,
                diastolic=105,
                measurement_time_text="2026-07-18T11:30:00+02:00",
                medication_taken="yes",
                missed_medication_reason=None,
                context_codes=[],
                unstructured_note=None,
                missing_fields=[],
                ambiguities=[],
                requires_confirmation=True,
            ),
            request_id="resp_real_whatsapp_test",
        )


class FakeWhatsAppGateway:
    configured = True
    webhook_configured = True

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sent: list[tuple[str, str]] = []
        self.fail_delivery = False

    def verify_token(self, supplied_token: str) -> bool:
        return supplied_token == "verify-test-token"

    def verify_signature(self, _body: bytes, signature: str | None) -> bool:
        return signature == "sha256=valid"

    def patient_for_sender(self, db: Session, sender: str):  # noqa: ANN201
        if sender != SENDER:
            return None
        return db.get(PatientProfile, PATIENT_IDS["rudo"])

    def destination_for_patient(self, patient: PatientProfile) -> str | None:
        return SENDER if patient.id == PATIENT_IDS["rudo"] else None

    def send_text(self, *, destination: str, content: str) -> str:
        if self.fail_delivery:
            from app.services.whatsapp import WhatsAppDeliveryError

            raise WhatsAppDeliveryError("synthetic failure")
        self.sent.append((destination, content))
        return "wamid.outbound.011"


def _payload(message_id: str = "wamid.inbound.011", sender: str = SENDER) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": sender,
                                    "id": message_id,
                                    "type": "text",
                                    "text": {"body": "I-BP yami ngu-168 over 105 ngo-11:30."},
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }


@pytest.fixture
def webhook_client(
    db_session: Session,
) -> Generator[tuple[TestClient, FakeWhatsAppGateway], None, None]:
    seed_demo_data(db_session, now=NOW)
    db_session.commit()
    gateway = FakeWhatsAppGateway(db_session)

    def override_database() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_database
    app.dependency_overrides[get_extraction_provider] = lambda: FakeProvider()
    app.dependency_overrides[get_whatsapp_gateway] = lambda: gateway
    client = TestClient(app)
    try:
        yield client, gateway
    finally:
        app.dependency_overrides.clear()


def test_webhook_verification_requires_the_configured_token(
    webhook_client: tuple[TestClient, FakeWhatsAppGateway],
) -> None:
    client, _gateway = webhook_client
    path = "/api/v1/channels/whatsapp/webhook"
    assert (
        client.get(
            path,
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "challenge-011",
            },
        ).status_code
        == 403
    )
    accepted = client.get(
        path,
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-test-token",
            "hub.challenge": "challenge-011",
        },
    )
    assert accepted.status_code == 200
    assert accepted.text == "challenge-011"


def test_signed_inbound_text_is_idempotent_and_sends_fixed_reply(
    webhook_client: tuple[TestClient, FakeWhatsAppGateway],
    db_session: Session,
) -> None:
    client, gateway = webhook_client
    headers = {"X-Hub-Signature-256": "sha256=valid"}
    path = "/api/v1/channels/whatsapp/webhook"
    assert client.post(path, json=_payload(), headers={}).status_code == 401

    first = client.post(path, json=_payload(), headers=headers)
    assert first.status_code == 200
    assert first.json()["processed_messages"] == 1
    assert first.json()["duplicate_messages"] == 0
    assert gateway.sent[0][0] == SENDER
    assert gateway.sent[0][1] == patient_text(Language.NDEBELE, "ready")
    assert db_session.scalar(select(func.count()).select_from(PatientMessage)) == 2

    inbound = db_session.scalar(
        select(PatientMessage).where(PatientMessage.provider_message_id == "wamid.inbound.011")
    )
    outbound = db_session.scalar(
        select(PatientMessage).where(PatientMessage.provider_message_id == "wamid.outbound.011")
    )
    assert inbound is not None and inbound.channel.value == "whatsapp_sandbox"
    assert outbound is not None and outbound.delivery_status is DeliveryStatus.SENT

    duplicate = client.post(path, json=_payload(), headers=headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["processed_messages"] == 0
    assert duplicate.json()["duplicate_messages"] == 1
    assert db_session.scalar(select(func.count()).select_from(PatientMessage)) == 2
    assert len(gateway.sent) == 1


def test_delivery_status_updates_and_unmapped_senders_are_non_disclosing(
    webhook_client: tuple[TestClient, FakeWhatsAppGateway],
    db_session: Session,
) -> None:
    client, _gateway = webhook_client
    headers = {"X-Hub-Signature-256": "sha256=valid"}
    path = "/api/v1/channels/whatsapp/webhook"
    client.post(path, json=_payload(), headers=headers)
    status_payload = {
        "entry": [
            {
                "changes": [
                    {"value": {"statuses": [{"id": "wamid.outbound.011", "status": "delivered"}]}}
                ]
            }
        ]
    }
    status_response = client.post(path, json=status_payload, headers=headers)
    assert status_response.json()["delivery_updates"] == 1
    outbound = db_session.scalar(
        select(PatientMessage).where(PatientMessage.provider_message_id == "wamid.outbound.011")
    )
    assert outbound is not None and outbound.delivery_status is DeliveryStatus.DELIVERED

    unknown = client.post(path, json=_payload("wamid.unknown", "263000000000"), headers=headers)
    assert unknown.status_code == 200
    assert unknown.json()["processed_messages"] == 0
    assert (
        db_session.scalar(
            select(PatientMessage).where(PatientMessage.provider_message_id == "wamid.unknown")
        )
        is None
    )


def test_meta_gateway_uses_constant_time_signature_and_phone_mapping(db_session: Session) -> None:
    seed_demo_data(db_session, now=NOW)
    db_session.commit()
    gateway = MetaWhatsAppGateway(
        enabled=True,
        api_version="v23.0",
        phone_number_id="synthetic-phone-id",
        access_token="synthetic-token",
        verify_token="synthetic-verify-token",
        app_secret="synthetic-app-secret",
        phone_map_json=f'{{"+{SENDER}": "10000000-0000-4000-8000-000000000002"}}',
    )
    body = b'{"synthetic":true}'
    signature = (
        "sha256="
        + hmac.new(
            b"synthetic-app-secret",
            body,
            hashlib.sha256,
        ).hexdigest()
    )

    assert gateway.configured is True
    assert gateway.webhook_configured is True
    assert gateway.verify_signature(body, signature) is True
    assert gateway.verify_signature(body + b"x", signature) is False
    patient = gateway.patient_for_sender(db_session, f"+{SENDER}")
    assert patient is not None and patient.id == PATIENT_IDS["rudo"]
