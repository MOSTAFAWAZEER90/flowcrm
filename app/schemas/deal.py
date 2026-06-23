from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import PipelineStage
from app.schemas.common import ORMModel


class DealCreate(BaseModel):
    contact_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    stage: PipelineStage = PipelineStage.new_lead
    value: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    owner_id: uuid.UUID | None = None
    probability: int = Field(default=0, ge=0, le=100)
    expected_close: date | None = None


class DealUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    stage: PipelineStage | None = None
    value: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    owner_id: uuid.UUID | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close: date | None = None
    lost_reason: str | None = None


class DealOut(ORMModel):
    id: uuid.UUID
    org_id: uuid.UUID
    contact_id: uuid.UUID
    title: str
    stage: PipelineStage
    value: Decimal
    currency: str
    owner_id: uuid.UUID | None = None
    probability: int
    expected_close: date | None = None
    lost_reason: str | None = None
    stage_changed_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StageHistoryOut(ORMModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    from_stage: PipelineStage | None = None
    to_stage: PipelineStage
    changed_by: uuid.UUID | None = None
    changed_at: datetime
