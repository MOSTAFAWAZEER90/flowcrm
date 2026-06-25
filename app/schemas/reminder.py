from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ReminderCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    remind_at: datetime
    message: str | None = Field(default=None, max_length=4000)
    channel: str = Field(default="whatsapp", max_length=40)


class ReminderOut(ORMModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    remind_at: datetime
    message: str | None = None
    channel: str
    status: str
    sent_at: datetime | None = None
    created_at: datetime


class ProcessResult(BaseModel):
    processed: int
    sent: int
    failed: int
