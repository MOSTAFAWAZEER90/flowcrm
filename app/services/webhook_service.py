"""Webhook signature verification and idempotent event capture."""
from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.channel_connection import ChannelConnection
from app.models.enums import LeadChannel
from app.models.webhook_event import WebhookEvent

log = get_logger("webhooks")

VALID_SOURCES = {"meta", "whatsapp", "calendly", "forms"}

SOURCE_CHANNEL: dict[str, LeadChannel] = {
    "meta": LeadChannel.messenger,
    "whatsapp": LeadChannel.whatsapp,
    "calendly": LeadChannel.calendly,
    "forms": LeadChannel.web_form,
}


def _hmac_sha256(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(source: str, body: bytes, headers: dict[str, str]) -> bool:
    """Verify the inbound webhook signature for the given source.

    If no secret is configured for the source, verification is skipped (dev mode)
    with a warning. Comparisons are constant-time.
    """
    secret = settings.webhook_secret(source)
    if not secret:
        log.warning("webhook_signature_skipped", source=source, reason="no secret configured")
        return True

    # Normalize header lookup to be case-insensitive.
    h = {k.lower(): v for k, v in headers.items()}

    if source == "calendly":
        raw = h.get("calendly-webhook-signature", "")
        parts = dict(p.split("=", 1) for p in raw.split(",") if "=" in p)
        timestamp, provided = parts.get("t"), parts.get("v1")
        if not timestamp or not provided:
            return False
        expected = _hmac_sha256(secret, f"{timestamp}.".encode() + body)
        return hmac.compare_digest(expected, provided)

    # Meta / WhatsApp use X-Hub-Signature-256: "sha256=<hex>"; forms use X-Signature.
    provided = h.get("x-hub-signature-256") or h.get("x-signature") or ""
    provided = provided.split("=", 1)[-1].strip()
    if not provided:
        return False
    expected = _hmac_sha256(secret, body)
    return hmac.compare_digest(expected, provided)


def extract_external_id(source: str, raw: dict[str, Any], body: bytes) -> str:
    """Best-effort stable id for idempotency; falls back to a body hash."""
    candidates: list[Any] = []
    try:
        if source in ("meta", "whatsapp"):
            entry = (raw.get("entry") or [{}])[0]
            candidates = [entry.get("id"), raw.get("id")]
            changes = (entry.get("changes") or [{}])[0]
            messages = ((changes.get("value") or {}).get("messages") or [{}])
            candidates.append(messages[0].get("id"))
        elif source == "calendly":
            payload = raw.get("payload") or {}
            candidates = [payload.get("uri"), raw.get("event"), raw.get("created_at")]
        elif source == "forms":
            candidates = [raw.get("id"), raw.get("submission_id"), raw.get("event_id")]
    except (AttributeError, IndexError, TypeError):
        candidates = []

    for c in candidates:
        if c:
            return str(c)
    return hashlib.sha256(body).hexdigest()


async def record_event(
    session: AsyncSession, *, source: str, external_id: str, raw: dict[str, Any]
) -> tuple[WebhookEvent | None, bool]:
    """Insert the event idempotently. Returns (event, is_new).

    ON CONFLICT (source, external_id) DO NOTHING gives idempotency; if nothing is
    returned the event was already seen.
    """
    stmt = (
        pg_insert(WebhookEvent)
        .values(source=source, external_id=external_id, raw=raw, processed=False)
        .on_conflict_do_nothing(index_elements=["source", "external_id"])
        .returning(WebhookEvent.id)
    )
    result = await session.execute(stmt)
    new_id = result.scalar_one_or_none()
    if new_id is None:
        return None, False
    event = await session.get(WebhookEvent, new_id)
    return event, True


# --------------------------------------------------------------------------- #
# Payload parsing (best-effort, used by the worker)
# --------------------------------------------------------------------------- #
def _first(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if d.get(k):
            return d[k]
    return None


def parse_contact_fields(source: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Extract contact-ish fields from a webhook body.

    Handles flat payloads (forms / n8n) plus a ``payload``/``data`` nesting. This
    is intentionally generic; tighten per provider as integrations are added.
    """
    body = raw
    nested = _first(raw, "payload", "data")
    if isinstance(nested, dict):
        body = {**raw, **nested}

    channel = SOURCE_CHANNEL.get(source, LeadChannel.web_form)
    return {
        "external_id": _first(body, "external_id", "id", "submission_id", "event_id", "uri"),
        "full_name": _first(body, "full_name", "name", "fullName") or "Unknown contact",
        "email": _first(body, "email", "email_address"),
        "phone": _first(body, "phone", "phone_number", "mobile"),
        "message": _first(body, "message", "text", "body", "notes"),
        "channel": channel,
        "external_thread": _first(body, "thread_id", "conversation_id", "uri"),
    }


async def resolve_org_id(
    session: AsyncSession, source: str, raw: dict[str, Any]
) -> uuid.UUID | None:
    """Resolve which org an event belongs to.

    Prefers an explicit org_id in the payload, otherwise matches a channel
    connection's external_id against likely identifiers in the body.
    """
    explicit = _first(raw, "org_id", "organization_id")
    if explicit:
        try:
            return uuid.UUID(str(explicit))
        except ValueError:
            pass

    candidates: list[str] = []
    entry = (raw.get("entry") or [{}])
    if isinstance(entry, list) and entry and isinstance(entry[0], dict):
        candidates.append(str(entry[0].get("id"))) if entry[0].get("id") else None
    for key in ("page_id", "phone_number_id", "connection_id", "account_id"):
        if raw.get(key):
            candidates.append(str(raw[key]))
    candidates = [c for c in candidates if c and c != "None"]
    if not candidates:
        return None

    channel = SOURCE_CHANNEL.get(source)
    result = await session.execute(
        select(ChannelConnection.org_id).where(
            ChannelConnection.channel == channel,
            ChannelConnection.external_id.in_(candidates),
        )
    )
    return result.scalars().first()
