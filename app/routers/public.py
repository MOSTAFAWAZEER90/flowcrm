"""Public, unauthenticated web-to-lead intake.

A landing-page form POSTs a lead here. The org is identified by its public slug
in the URL. The lead is upserted (idempotent) under that tenant, seeding a
conversation + first message and running AI scoring — exactly like the n8n path.

NOTE: this endpoint is intentionally unauthenticated. For production, add a
per-org public form token and rate limiting to prevent abuse.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.core.deps import Principal, SystemSession
from app.models.enums import LeadChannel, UserRole
from app.repositories.organization_repo import OrganizationRepository
from app.schemas.contact import ContactUpsert
from app.schemas.public import PublicLeadIn, PublicLeadResult
from app.services.contact_service import ContactService
from app.workers.queue import scoped_worker_session

router = APIRouter(prefix="/public", tags=["public"])


@router.post("/leads/{org_slug}", response_model=PublicLeadResult)
async def capture_lead(
    org_slug: str, payload: PublicLeadIn, system: SystemSession
) -> PublicLeadResult:
    # Resolve the tenant by slug (RLS bypassed on the system session).
    await system.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
    org = await OrganizationRepository(system).get_by_slug(org_slug)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown organization")

    # Idempotency key: prefer email, then phone, else a fresh id.
    external_id = payload.email or payload.phone or f"web-{uuid.uuid4().hex}"
    principal = Principal(
        user_id=uuid.UUID(int=0), org_id=org.id, role=UserRole.admin, email="public@web-form"
    )

    async with scoped_worker_session(org.id) as session:
        contact, created, is_hot = await ContactService(session, principal).upsert(
            ContactUpsert(
                external_id=external_id,
                full_name=payload.full_name,
                email=payload.email,
                phone=payload.phone,
                channel=LeadChannel.web_form,
                message=payload.message,
            )
        )
        contact_id = str(contact.id)

    return PublicLeadResult(
        ok=True, created=created, is_hot_lead=is_hot, contact_id=contact_id
    )
