from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EnrollRequest(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    template: str = Field(default="default", max_length=120)


class AdvanceRequest(BaseModel):
    sequence_id: uuid.UUID
    sent_step: int = Field(ge=1, le=4)


class CompleteRequest(BaseModel):
    sequence_id: uuid.UUID
    reason: str = Field(default="completed", max_length=255)


class SequenceOut(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    template: str
    current_step: int
    next_run_at: datetime | None = None
    is_active: bool


class DueSequenceOut(BaseModel):
    sequence_id: uuid.UUID
    contact_id: uuid.UUID
    template: str
    current_step: int
    next_step: int
    next_run_at: datetime | None = None
    contact_replied: bool
    contact_name: str
    contact_email: str | None = None
    contact_phone: str | None = None
