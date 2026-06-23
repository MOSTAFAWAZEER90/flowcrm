from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal
from app.core.errors import NotFoundError
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import ContactStatus, LeadChannel, MessageDirection
from app.models.message import Message
from app.repositories.contact_repo import ContactRepository
from app.schemas.contact import ContactCreate, ContactUpdate, ContactUpsert
from app.services import ai_service
from app.services.ai_service import Classification
from app.services.scoring import ScoreFeatures, blend_lead_score, is_hot_lead


def _recency_hours(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0)


def compute_score(contact: Contact, classification: Classification) -> int:
    """Blend the AI base score with the contact's deterministic features."""
    features = ScoreFeatures(
        ai_base_score=classification.ai_base_score,
        channel=contact.source,
        recency_hours=_recency_hours(contact.last_activity_at),
        has_email=bool(contact.email),
        has_phone=bool(contact.phone),
        has_name=bool(contact.full_name),
        buying_signal=classification.buying_signal,
    )
    return blend_lead_score(features)


class ContactService:
    def __init__(self, session: AsyncSession, principal: Principal):
        self.session = session
        self.principal = principal
        self.repo = ContactRepository(session)

    async def get(self, contact_id: uuid.UUID) -> Contact:
        contact = await self.repo.get_active(contact_id)
        if contact is None:
            raise NotFoundError("Contact not found")
        return contact

    async def create(self, payload: ContactCreate) -> Contact:
        contact = Contact(
            org_id=self.principal.org_id,
            full_name=payload.full_name,
            email=str(payload.email).lower() if payload.email else None,
            phone=payload.phone,
            source=payload.source,
            status=payload.status,
            tags=payload.tags,
            assigned_to=payload.assigned_to,
            external_refs=payload.external_refs,
            custom_fields=payload.custom_fields,
            last_activity_at=datetime.now(timezone.utc),
        )
        return await self.repo.add(contact)

    async def update(self, contact_id: uuid.UUID, payload: ContactUpdate) -> Contact:
        contact = await self.get(contact_id)
        data = payload.model_dump(exclude_unset=True)
        if "email" in data and data["email"]:
            data["email"] = str(data["email"]).lower()
        for key, value in data.items():
            setattr(contact, key, value)
        await self.session.flush()
        return contact

    async def list(self, **filters) -> tuple[list[Contact], int]:
        return await self.repo.search(**filters)

    async def upsert(self, payload: ContactUpsert) -> tuple[Contact, bool, bool]:
        """Idempotent by external_id. On insert: create conversation + first
        message and run AI scoring. On match: refresh basic fields."""
        existing = await self.repo.find_by_external_id(payload.external_id)
        now = datetime.now(timezone.utc)

        if existing is not None:
            existing.full_name = payload.full_name or existing.full_name
            if payload.email:
                existing.email = str(payload.email).lower()
            if payload.phone:
                existing.phone = payload.phone
            if payload.tags:
                existing.tags = sorted(set(existing.tags) | set(payload.tags))
            if payload.custom_fields:
                existing.custom_fields = {**existing.custom_fields, **payload.custom_fields}
            existing.last_activity_at = now
            await self.session.flush()
            return existing, False, is_hot_lead(existing.lead_score, False)

        # --- New contact ---
        contact = Contact(
            org_id=self.principal.org_id,
            full_name=payload.full_name,
            email=str(payload.email).lower() if payload.email else None,
            phone=payload.phone,
            source=payload.channel,
            status=ContactStatus.active,
            tags=payload.tags,
            external_refs={"external_id": payload.external_id},
            custom_fields=payload.custom_fields,
            last_activity_at=now,
        )
        await self.repo.add(contact)

        conversation = Conversation(
            org_id=self.principal.org_id,
            contact_id=contact.id,
            channel=payload.channel,
            external_thread=payload.external_thread,
            is_open=True,
            last_message_at=now,
            unread_count=1 if payload.message else 0,
        )
        self.session.add(conversation)
        await self.session.flush()

        # AI scoring on the first inbound message (falls back to the name).
        text = payload.message or payload.full_name
        classification = await ai_service.classify(text)

        if payload.message:
            message = Message(
                org_id=self.principal.org_id,
                conversation_id=conversation.id,
                direction=MessageDirection.inbound,
                body=payload.message,
                ai_intent=classification.intent,
                ai_sentiment=_intent_sentiment(classification),
            )
            self.session.add(message)

        contact.lead_score = compute_score(contact, classification)
        hot = is_hot_lead(contact.lead_score, classification.buying_signal)
        await self.session.flush()
        return contact, True, hot


def _intent_sentiment(classification: Classification) -> Decimal:
    """Coarse sentiment proxy derived from intent (range -1..1)."""
    positive = {"ready_to_buy", "booking", "pricing", "inquiry"}
    negative = {"complaint", "not_interested", "spam"}
    if classification.intent.value in positive:
        return Decimal("0.6")
    if classification.intent.value in negative:
        return Decimal("-0.6")
    return Decimal("0.0")
