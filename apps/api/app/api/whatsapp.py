import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel
from app.services.ai_extraction import ExtractionProvider, get_extraction_provider
from app.services.conversations import send_conversation_message
from app.services.whatsapp import (
    WhatsAppDeliveryError,
    WhatsAppGateway,
    apply_delivery_statuses,
    get_whatsapp_gateway,
    mark_outbound_delivery,
    normalise_inbound_texts,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/channels/whatsapp", tags=["whatsapp"])

DatabaseSession = Annotated[Session, Depends(get_db)]
ExtractionProviderDependency = Annotated[ExtractionProvider, Depends(get_extraction_provider)]
WhatsAppGatewayDependency = Annotated[WhatsAppGateway, Depends(get_whatsapp_gateway)]


@router.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(
    gateway: WhatsAppGatewayDependency,
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> str:
    if (
        mode != "subscribe"
        or verify_token is None
        or challenge is None
        or not gateway.verify_token(verify_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed"
        )
    return challenge


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    db: DatabaseSession,
    provider: ExtractionProviderDependency,
    gateway: WhatsAppGatewayDependency,
    signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> dict[str, object]:
    if not gateway.webhook_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp webhook is not configured",
        )
    body = await request.body()
    if not gateway.verify_signature(body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload"
        )

    processed = 0
    duplicate = 0
    delivery_updates = apply_delivery_statuses(db, payload)
    for inbound in normalise_inbound_texts(payload):
        patient = gateway.patient_for_sender(db, inbound.sender)
        if patient is None:
            logger.warning("whatsapp_sender_not_mapped")
            continue
        patient.preferred_channel = Channel.WHATSAPP_SANDBOX
        response, system_message = send_conversation_message(
            db,
            patient=patient,
            actor_user_id=patient.user_id,
            content=inbound.content,
            provider=provider,
            channel=Channel.WHATSAPP_SANDBOX,
            provider_message_id=inbound.provider_message_id,
            real_whatsapp_configured=True,
        )
        if response.duplicate_provider_message:
            duplicate += 1
            continue
        processed += 1
        if system_message is None:
            continue
        try:
            outbound_id = gateway.send_text(
                destination=inbound.sender,
                content=system_message.content,
            )
            mark_outbound_delivery(
                system_message,
                provider_message_id=outbound_id,
                delivered=True,
            )
        except WhatsAppDeliveryError:
            mark_outbound_delivery(
                system_message,
                provider_message_id=None,
                delivered=False,
            )
            logger.warning("whatsapp_outbound_delivery_failed")
    db.commit()
    return {
        "accepted": True,
        "processed_messages": processed,
        "duplicate_messages": duplicate,
        "delivery_updates": delivery_updates,
    }
