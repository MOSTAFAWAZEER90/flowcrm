from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import AIIntent, LeadChannel, MessageDirection
from app.schemas.common import ORMModel


class ConversationOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    contact_id: uuid.UUID
    channel: LeadChannel
    connection_id: uuid.UUID | None = None
    external_thread: str | None = None
    is_open: bool
    last_message_at: datetime | None = None
    unread_count: int
    created_at: datetime


class MessageOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    conversation_id: uuid.UUID
    direction: MessageDirection
    sender_user_id: uuid.UUID | None = None
    body: str | None = None
    attachments: list[Any]
    external_id: str | None = None
    ai_intent: AIIntent | None = None
    ai_sentiment: Decimal | None = None
    created_at: datetime


class OutboundMessageCreate(BaseModel):
    body: str = Field(min_length=1)
    attachments: list[Any] = Field(default_factory=list)
    external_id: str | None = Field(default=None, max_length=255)
