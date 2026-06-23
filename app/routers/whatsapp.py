"""WhatsApp Cloud API (Meta) webhook.

Meta verifies the webhook with a GET challenge, then POSTs inbound messages.
Each message is turned into a contact (idempotent upsert) under the org named
by WHATSAPP_ORG_SLUG, seeding a conversation + first message + AI scoring.

NOTE: processing runs inline (the deployed instance has no ARQ worker). Fine for
typical volumes; move to a queue if traffic grows.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import PlainTextResponse

from sqlalchemy import text

from app.core.config import settings
from app.core.deps import Principal, SystemSession
from app.core.logging import get_logger
from app.models.enums import LeadChannel, UserRole
from app.repositories.organization_repo import OrganizationRepository
from app.schemas.contact import ContactUpsert
from app.services.contact_service import ContactService
from app.workers.queue import scoped_worker_session

log = get_logger("whatsapp")
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.get("/webhook")
async def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    """Meta webhook verification handshake."""
    if mode == "subscribe" and token and token == settings.whatsapp_verify_token:
        return PlainTextResponse(challenge or "")
    return PlainTextResponse("verification failed", status_code=status.HTTP_403_FORBIDDEN)


def _parse_inbound(body: dict) -> tuple[str | None, str | None, str | None]:
    """Return (message_text, sender_phone, sender_name) from a Meta payload."""
    try:
        value = body["entry"][0]["changes"][0]["value"]
        contacts = value.get("contacts") or []
        name = (contacts[0].get("profile") or {}).get("name") if contacts else None
        messages = value.get("messages") or []
        if not messages:
            return None, None, name  # delivery/status callback, not a message
        msg = messages[0]
        phone = msg.get("from")
        text_body = (msg.get("text") or {}).get("body")
        return text_body, phone, name
    except (KeyError, IndexError, TypeError):
        return None, None, None


@router.post("/webhook")
async def receive_webhook(request: Request, system: SystemSession) -> dict:
    body = await request.json()
    text_body, phone, name = _parse_inbound(body)

    # Ignore non-message callbacks (delivery receipts, read status, etc.)
    if not phone and not text_body:
        return {"status": "ignored"}

    # Resolve the receiving tenant.
    await system.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
    org = await OrganizationRepository(system).get_by_slug(settings.whatsapp_org_slug)
    if org is None:
        log.warning("whatsapp_no_org", slug=settings.whatsapp_org_slug)
        return {"status": "no_org"}

    principal = Principal(
        user_id=uuid.UUID(int=0), org_id=org.id, role=UserRole.admin, email="whatsapp@system"
    )
    external_id = phone or name or f"wa-{uuid.uuid4().hex}"
    async with scoped_worker_session(org.id) as session:
        contact, created, is_hot = await ContactService(session, principal).upsert(
            ContactUpsert(
                external_id=external_id,
                full_name=name or phone or "WhatsApp lead",
                phone=phone,
                channel=LeadChannel.whatsapp,
                message=text_body,
            )
        )
    log.info("whatsapp_lead", created=created, is_hot=is_hot, phone=phone)
    return {"status": "received", "created": created}
