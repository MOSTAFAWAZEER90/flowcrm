"""Idempotent upsert: same external_id never creates a second contact, and the
first insert seeds a conversation + first message and runs AI scoring."""
from __future__ import annotations

import uuid

from app.core.deps import Principal
from app.models.enums import LeadChannel, UserRole
from app.repositories.contact_repo import ContactRepository
from app.repositories.conversation_repo import ConversationRepository, MessageRepository
from app.schemas.contact import ContactUpsert
from app.services.contact_service import ContactService


async def test_upsert_is_idempotent_by_external_id(org_factory, scoped_session):
    org_id, user_id = await org_factory()
    principal = Principal(user_id=user_id, org_id=org_id, role=UserRole.admin, email="a@b.c")
    external_id = uuid.uuid4().hex

    payload = ContactUpsert(
        external_id=external_id,
        full_name="Jane Doe",
        email="jane@example.com",
        phone="+15551234567",
        channel=LeadChannel.whatsapp,
        message="Hi! What's the pricing for the pro plan?",
    )

    # First upsert -> creates contact + conversation + message + score.
    async with scoped_session(org_id, user_id) as session:
        contact1, created1, hot1 = await ContactService(session, principal).upsert(payload)
        first_id = contact1.id
        first_score = contact1.lead_score

    assert created1 is True
    assert hot1 is True  # pricing intent => buying signal => hot
    assert first_score > 0

    # Second upsert with the same external_id -> updates, does NOT duplicate.
    async with scoped_session(org_id, user_id) as session:
        contact2, created2, _ = await ContactService(session, principal).upsert(payload)
        second_id = contact2.id

    assert created2 is False
    assert second_id == first_id

    # Exactly one contact exists for this org.
    async with scoped_session(org_id) as session:
        _, total = await ContactRepository(session).search()
        assert total == 1

    # The first insert seeded one conversation with one inbound message.
    async with scoped_session(org_id) as session:
        conversation = await ConversationRepository(session).get_for_contact(first_id)
        assert conversation is not None
        messages = await MessageRepository(session).list_for_conversation(conversation.id)
        assert len(messages) == 1
        assert messages[0].body == payload.message
        assert messages[0].ai_intent is not None
