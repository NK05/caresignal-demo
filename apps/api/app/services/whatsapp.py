import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DeliveryStatus, PatientMessage, PatientProfile

logger = logging.getLogger(__name__)


class WhatsAppDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class WhatsAppInboundText:
    provider_message_id: str
    sender: str
    content: str


class WhatsAppGateway(Protocol):
    @property
    def configured(self) -> bool: ...

    @property
    def webhook_configured(self) -> bool: ...

    def verify_token(self, supplied_token: str) -> bool: ...

    def verify_signature(self, body: bytes, signature: str | None) -> bool: ...

    def patient_for_sender(self, db: Session, sender: str) -> PatientProfile | None: ...

    def destination_for_patient(self, patient: PatientProfile) -> str | None: ...

    def send_text(self, *, destination: str, content: str) -> str: ...


def _normalise_phone(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


class MetaWhatsAppGateway:
    def __init__(
        self,
        *,
        enabled: bool,
        api_version: str,
        phone_number_id: str | None,
        access_token: str | None,
        verify_token: str | None,
        app_secret: str | None,
        phone_map_json: str,
    ) -> None:
        self._enabled = enabled
        self._api_version = api_version
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._verify_token = verify_token
        self._app_secret = app_secret
        try:
            raw_map = json.loads(phone_map_json)
            if not isinstance(raw_map, dict):
                raise ValueError("phone map must be an object")
            self._phone_map = {
                _normalise_phone(str(phone)): str(user_id)
                for phone, user_id in raw_map.items()
                if _normalise_phone(str(phone))
            }
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("whatsapp_phone_map_invalid")
            self._phone_map = {}

    @property
    def configured(self) -> bool:
        return bool(
            self._enabled and self._phone_number_id and self._access_token and self._phone_map
        )

    @property
    def webhook_configured(self) -> bool:
        return bool(self.configured and self._verify_token and self._app_secret)

    def verify_token(self, supplied_token: str) -> bool:
        return bool(self._verify_token and hmac.compare_digest(supplied_token, self._verify_token))

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        if not self._app_secret or not signature or not signature.startswith("sha256="):
            return False
        expected = (
            "sha256="
            + hmac.new(
                self._app_secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()
        )
        return hmac.compare_digest(signature, expected)

    def patient_for_sender(self, db: Session, sender: str) -> PatientProfile | None:
        user_id = self._phone_map.get(_normalise_phone(sender))
        if user_id is None:
            return None
        return db.scalar(select(PatientProfile).where(PatientProfile.user_id == user_id))

    def destination_for_patient(self, patient: PatientProfile) -> str | None:
        return next(
            (phone for phone, user_id in self._phone_map.items() if user_id == patient.user_id),
            None,
        )

    def send_text(self, *, destination: str, content: str) -> str:
        if not self.configured or not self._phone_number_id or not self._access_token:
            raise WhatsAppDeliveryError("WhatsApp delivery is not configured")
        url = f"https://graph.facebook.com/{self._api_version}/{self._phone_number_id}/messages"
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": _normalise_phone(destination),
                    "type": "text",
                    "text": {"preview_url": False, "body": content},
                },
                timeout=10.0,
            )
            response.raise_for_status()
            body = response.json()
            provider_id = body["messages"][0]["id"]
            if not isinstance(provider_id, str) or not provider_id:
                raise ValueError("missing provider message id")
            return provider_id
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise WhatsAppDeliveryError("WhatsApp delivery failed") from exc


@lru_cache
def get_whatsapp_gateway() -> WhatsAppGateway:
    settings = get_settings()
    return MetaWhatsAppGateway(
        enabled=settings.whatsapp_cloud_api_enabled,
        api_version=settings.whatsapp_cloud_api_version,
        phone_number_id=settings.whatsapp_phone_number_id,
        access_token=settings.whatsapp_access_token,
        verify_token=settings.whatsapp_verify_token,
        app_secret=settings.whatsapp_app_secret,
        phone_map_json=settings.whatsapp_demo_phone_map,
    )


def normalise_inbound_texts(payload: dict[str, Any]) -> list[WhatsAppInboundText]:
    inbound: list[WhatsAppInboundText] = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return inbound
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            messages = value.get("messages")
            if not isinstance(messages, list):
                continue
            for message in messages:
                if not isinstance(message, dict) or message.get("type") != "text":
                    continue
                text = message.get("text")
                provider_id = message.get("id")
                sender = message.get("from")
                content = text.get("body") if isinstance(text, dict) else None
                if all(
                    isinstance(item, str) and item.strip()
                    for item in (provider_id, sender, content)
                ):
                    inbound.append(
                        WhatsAppInboundText(
                            provider_message_id=provider_id.strip(),
                            sender=sender.strip(),
                            content=content.strip(),
                        )
                    )
    return inbound


def apply_delivery_statuses(db: Session, payload: dict[str, Any]) -> int:
    updated = 0
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return updated
    for entry in entries:
        changes = entry.get("changes") if isinstance(entry, dict) else None
        if not isinstance(changes, list):
            continue
        for change in changes:
            value = change.get("value") if isinstance(change, dict) else None
            statuses = value.get("statuses") if isinstance(value, dict) else None
            if not isinstance(statuses, list):
                continue
            for status_payload in statuses:
                if not isinstance(status_payload, dict):
                    continue
                provider_id = status_payload.get("id")
                provider_status = status_payload.get("status")
                if not isinstance(provider_id, str) or not isinstance(provider_status, str):
                    continue
                message = db.scalar(
                    select(PatientMessage).where(PatientMessage.provider_message_id == provider_id)
                )
                if message is None:
                    continue
                mapped_status = {
                    "sent": DeliveryStatus.SENT,
                    "delivered": DeliveryStatus.DELIVERED,
                    "read": DeliveryStatus.DELIVERED,
                    "failed": DeliveryStatus.DELIVERY_FAILED,
                }.get(provider_status)
                if mapped_status is not None:
                    message.delivery_status = mapped_status
                    updated += 1
    return updated


def mark_outbound_delivery(
    message: PatientMessage,
    *,
    provider_message_id: str | None,
    delivered: bool,
) -> None:
    if delivered and provider_message_id:
        message.provider_message_id = provider_message_id
        message.delivery_status = DeliveryStatus.SENT
        message.sent_at = message.updated_at
    else:
        message.delivery_status = DeliveryStatus.DELIVERY_FAILED
