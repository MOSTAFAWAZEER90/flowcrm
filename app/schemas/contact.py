from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import ContactStatus, LeadChannel
from app.schemas.common import ORMModel


class ContactBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    source: LeadChannel = LeadChannel.manual
    status: ContactStatus = ContactStatus.active
    tags: list[str] = Field(default_factory=list)
    assigned_to: uuid.UUID | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class ContactCreate(ContactBase):
    external_refs: dict[str, Any] = Field(default_factory=dict)


class ContactUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    status: ContactStatus | None = None
    lead_score: int | None = Field(default=None, ge=0, le=100)
    tags: list[str] | None = None
    assigned_to: uuid.UUID | None = None
    custom_fields: dict[str, Any] | None = None


class ContactUpsert(BaseModel):
    """Idempotent payload from n8n, keyed by external_id."""

    external_id: str = Field(min_length=1, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    channel: LeadChannel = LeadChannel.manual
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    # Optional first inbound message to seed the conversation.
    message: str | None = None
    external_thread: str | None = Field(default=None, max_length=255)


class ContactOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    full_name: str
    email: str | None = None
    phone: str | None = None
    source: LeadChannel
    status: ContactStatus
    lead_score: int
    tags: list[str]
    assigned_to: uuid.UUID | None = None
    external_refs: dict[str, Any]
    custom_fields: dict[str, Any]
    last_activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ContactUpsertResult(BaseModel):
    contact: ContactOut
    created: bool
    is_hot_lead: bool
