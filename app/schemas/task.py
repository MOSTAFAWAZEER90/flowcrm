from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import TaskStatus
from app.schemas.common import ORMModel


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    contact_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    # Either an absolute due date or a relative offset in minutes.
    due_at: datetime | None = None
    due_in_minutes: int | None = Field(default=None, ge=0)
    created_by_ai: bool = False

    @model_validator(mode="after")
    def _check_due(self) -> "TaskCreate":
        if self.due_at is not None and self.due_in_minutes is not None:
            raise ValueError("Provide only one of due_at or due_in_minutes")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    assigned_to: uuid.UUID | None = None
    due_at: datetime | None = None
    status: TaskStatus | None = None


class TaskOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    title: str
    description: str | None = None
    due_at: datetime | None = None
    status: TaskStatus
    created_by_ai: bool
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
