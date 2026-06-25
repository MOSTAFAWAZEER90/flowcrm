"""Facebook Page comments -> AI reply + private message (feature #6, ManyChat-style).

Meta sends 'feed' webhook events when someone comments on a page post. We reply
publicly under the comment (human-worded, per feature #1), open a private message
to continue the conversation, and capture the commenter as a lead with their
Facebook profile link (feature #3). Requires a Page access token + the page
subscribed to the 'feed' webhook field.
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
from app.models.webhook_event import WebhookEvent
from app.repositories.organization_repo import OrganizationRepository
from app.schemas.contact import ContactUpsert
from app.services import ai_service, messaging
from app.services.contact_service import ContactService
from app.workers.queue import scoped_worker_session

log = get_logger("facebook")
router = APIRouter(prefix="/facebook", tags=["facebook"])


@router.get("/webhook")
async def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    if mode == "subscribe" and token and token == settings.facebook_verify_token:
        return PlainTextResponse(challenge or "")
    return PlainTextResponse("verification failed", status_code=status.HTTP_403_FORBIDDEN)


@router.post("/webhook")
async def receive_webhook(request: Request, system: SystemSession) -> dict:
    body = await request.json()
    system.add(
        WebhookEvent(source="facebook", external_id=uuid.uuid4().hex, raw=body, processed=False)
    )
    await system.commit()

    if body.get("object") != "page":
        return {"status": "ignored"}

    await system.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
    org = await OrganizationRepository(system).get_by_slug(settings.facebook_org_slug)
    if org is None:
        return {"status": "no_org"}

    principal = Principal(
        user_id=uuid.UUID(int=0), org_id=org.id, role=UserRole.admin, email="facebook@system"
    )
    handled = 0

    for entry in body.get("entry", []):
        page_id = str(entry.get("id"))
        for change in entry.get("changes", []):
            if change.get("field") != "feed":
                continue
            value = change.get("value", {})
            if value.get("item") != "comment" or value.get("verb") != "add":
                continue
            frm = value.get("from", {}) or {}
            from_id = str(frm.get("id", ""))
            if not from_id or from_id == page_id:  # skip the page's own comments
                continue

            comment_id = value.get("comment_id") or value.get("id")
            message = value.get("message", "")
            name = frm.get("name")

            # Human reply (persona + no-AI rules from feature #1/#7).
            classification = await ai_service.classify(message)
            public_reply = classification.suggested_reply or "أهلاً بيك 🙏 بعتلك رسالة على الخاص."
            if comment_id:
                await messaging.fb_reply_to_comment(comment_id, public_reply)
                await messaging.fb_private_reply(
                    comment_id, f"{public_reply}\nكلّمني هنا على الخاص وأكمّل معاك على طول 🙏"
                )

            # Capture the commenter as a lead with their FB profile link (#3).
            async with scoped_worker_session(org.id) as session:
                contact, _, _ = await ContactService(session, principal).upsert(
                    ContactUpsert(
                        external_id=from_id,
                        full_name=name or "عميل من فيسبوك",
                        channel=LeadChannel.messenger,
                        message=message,
                    )
                )
                contact.external_refs = {
                    **(contact.external_refs or {}),
                    "external_id": from_id,
                    "profile_url": f"https://facebook.com/{from_id}",
                }
            handled += 1

    return {"status": "processed", "comments": handled}
