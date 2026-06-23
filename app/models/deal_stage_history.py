from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, UUIDPKMixin
from app.models.enums import PipelineStage, pg_enum


class DealStageHistory(UUIDPKMixin, OrgScopedMixin, Base):
    __tablename__ = "deal_stage_history"

    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_stage: Mapped[PipelineStage | None] = mapped_column(
        pg_enum(PipelineStage, "pipeline_stage"), nullable=True
    )
    to_stage: Mapped[PipelineStage] = mapped_column(
        pg_enum(PipelineStage, "pipeline_stage"), nullable=False
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
