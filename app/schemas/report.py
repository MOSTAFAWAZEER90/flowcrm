from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel


class FunnelStage(BaseModel):
    stage: str
    count: int


class FunnelReport(BaseModel):
    stages: list[FunnelStage]
    total_contacts: int


class PipelineStageValue(BaseModel):
    stage: str
    count: int
    total_value: Decimal
    weighted_value: Decimal


class PipelineReport(BaseModel):
    stages: list[PipelineStageValue]
    open_value: Decimal
    won_value: Decimal


class SourceBreakdown(BaseModel):
    source: str
    count: int
    won: int


class SourcesReport(BaseModel):
    sources: list[SourceBreakdown]


class TeamMemberStats(BaseModel):
    user_id: uuid.UUID | None
    full_name: str | None
    open_deals: int
    won_deals: int
    won_value: Decimal
    open_tasks: int


class TeamReport(BaseModel):
    members: list[TeamMemberStats]
