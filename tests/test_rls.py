"""Row Level Security: org A cannot read org B's data, and cross-tenant writes
are rejected by the RLS WITH CHECK policy."""
from __future__ import annotations

import pytest

from app.models.contact import Contact
from app.models.enums import ContactStatus, LeadChannel
from app.repositories.contact_repo import ContactRepository


async def test_org_cannot_read_other_orgs_contacts(org_factory, scoped_session):
    org_a, user_a = await org_factory()
    org_b, user_b = await org_factory()

    # Org A creates a contact.
    async with scoped_session(org_a, user_a) as session:
        contact = Contact(
            org_id=org_a,
            full_name="A-Org Lead",
            source=LeadChannel.manual,
            status=ContactStatus.active,
        )
        session.add(contact)
        await session.flush()
        a_contact_id = contact.id

    # Org B sees none of A's contacts.
    async with scoped_session(org_b, user_b) as session:
        repo = ContactRepository(session)
        _, total_b = await repo.search()
        assert total_b == 0
        assert await repo.get_active(a_contact_id) is None

    # Org A still sees its own contact.
    async with scoped_session(org_a, user_a) as session:
        repo = ContactRepository(session)
        _, total_a = await repo.search()
        assert total_a == 1
        assert await repo.get_active(a_contact_id) is not None


async def test_cross_tenant_insert_is_rejected(org_factory, scoped_session):
    org_a, _ = await org_factory()
    org_b, user_b = await org_factory()

    # While scoped to org B, attempt to insert a row owned by org A.
    with pytest.raises(Exception):
        async with scoped_session(org_b, user_b) as session:
            session.add(
                Contact(
                    org_id=org_a,  # violates RLS WITH CHECK for current_org=org_b
                    full_name="Cross-tenant injection",
                    source=LeadChannel.manual,
                    status=ContactStatus.active,
                )
            )
            await session.flush()
