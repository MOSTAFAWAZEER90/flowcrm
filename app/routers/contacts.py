from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentPrincipal, DBSession
from app.models.enums import ContactStatus, LeadChannel
from app.schemas.common import Page
from app.schemas.contact import (
    ContactCreate,
    ContactOut,
    ContactUpdate,
    ContactUpsert,
    ContactUpsertResult,
)
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=Page[ContactOut])
async def list_contacts(
    session: DBSession,
    principal: CurrentPrincipal,
    search: str | None = Query(default=None, description="Match name or email"),
    status_filter: ContactStatus | None = Query(default=None, alias="status"),
    source: LeadChannel | None = None,
    assigned_to: uuid.UUID | None = None,
    tag: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[ContactOut]:
    service = ContactService(session, principal)
    items, total = await service.list(
        search=search,
        status=status_filter,
        source=source,
        assigned_to=assigned_to,
        tag=tag,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[ContactOut.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactCreate, session: DBSession, principal: CurrentPrincipal
) -> ContactOut:
    service = ContactService(session, principal)
    contact = await service.create(payload)
    return ContactOut.model_validate(contact)


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    session: DBSession,
    principal: CurrentPrincipal,
) -> ContactOut:
    service = ContactService(session, principal)
    contact = await service.update(contact_id, payload)
    return ContactOut.model_validate(contact)


@router.post("/upsert", response_model=ContactUpsertResult)
async def upsert_contact(
    payload: ContactUpsert, session: DBSession, principal: CurrentPrincipal
) -> ContactUpsertResult:
    """Idempotent by external_id (called by n8n). On first insert this also
    creates a conversation + first message and runs AI lead scoring."""
    service = ContactService(session, principal)
    contact, created, is_hot = await service.upsert(payload)
    return ContactUpsertResult(
        contact=ContactOut.model_validate(contact), created=created, is_hot_lead=is_hot
    )
