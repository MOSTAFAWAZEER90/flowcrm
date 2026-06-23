"""ARQ task functions."""
from __future__ import annotations

import uuid

from sqlalchemy import text

from app.core.db import AsyncSessionLocal
from app.core.deps import Principal
from app.core.logging import get_logger
from app.models.enums import UserRole
from app.models.webhook_event import WebhookEvent
from app.schemas.contact import ContactUpsert
from app.services import webhook_service
from app.services.contact_service import ContactService
from app.workers.queue import scoped_worker_session

log = get_logger("worker")

# Synthetic principal for system-initiated writes (org filled in per event).
_SYSTEM_USER_ID = uuid.UUID(int=0)


async def process_webhook(ctx: dict, event_id: str) -> dict:
    """Parse a stored webhook event into a contact (idempotent)."""
    eid = uuid.UUID(event_id)

    # System session: opt out of RLS to load the event + resolve its org
    # (webhook_events has no org context yet, and channel lookup spans tenants).
    async with AsyncSessionLocal() as system:
        await system.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        event = await system.get(WebhookEvent, eid)
        if event is None:
            log.warning("webhook_event_missing", event_id=event_id)
            return {"status": "missing"}
        if event.processed:
            return {"status": "already_processed"}

        org_id = event.org_id or await webhook_service.resolve_org_id(
            system, event.source, event.raw
        )
        fields = webhook_service.parse_contact_fields(event.source, event.raw)

        if org_id is None or not fields.get("external_id"):
            event.processed = True
            await system.commit()
            log.warning("webhook_unattributed", source=event.source, event_id=event_id)
            return {"status": "unattributed"}

    # Tenant-scoped session (RLS enforced) for the actual upsert.
    principal = Principal(
        user_id=_SYSTEM_USER_ID, org_id=org_id, role=UserRole.admin, email="webhook@system"
    )
    async with scoped_worker_session(org_id) as session:
        service = ContactService(session, principal)
        contact, created, is_hot = await service.upsert(
            ContactUpsert(
                external_id=str(fields["external_id"]),
                full_name=fields["full_name"],
                email=fields["email"],
                phone=fields["phone"],
                channel=fields["channel"],
                message=fields["message"],
                external_thread=fields["external_thread"],
            )
        )
        contact_id = str(contact.id)

    # Mark processed on the owner session.
    async with AsyncSessionLocal() as system:
        event = await system.get(WebhookEvent, eid)
        if event is not None:
            event.processed = True
            event.org_id = org_id
            await system.commit()

    log.info(
        "webhook_processed",
        source=fields["channel"].value,
        contact_id=contact_id,
        created=created,
        is_hot=is_hot,
    )
    return {"status": "processed", "contact_id": contact_id, "created": created}
