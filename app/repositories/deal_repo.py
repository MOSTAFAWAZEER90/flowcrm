from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.models.deal_stage_history import DealStageHistory
from app.models.enums import PipelineStage
from app.repositories.base import BaseRepository


class DealRepository(BaseRepository[Deal]):
    model = Deal

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    def _filtered(
        self,
        *,
        stage: PipelineStage | None,
        owner_id: uuid.UUID | None,
        contact_id: uuid.UUID | None,
    ) -> Select:
        stmt = select(Deal)
        if stage is not None:
            stmt = stmt.where(Deal.stage == stage)
        if owner_id is not None:
            stmt = stmt.where(Deal.owner_id == owner_id)
        if contact_id is not None:
            stmt = stmt.where(Deal.contact_id == contact_id)
        return stmt

    async def search(
        self,
        *,
        stage: PipelineStage | None = None,
        owner_id: uuid.UUID | None = None,
        contact_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Deal], int]:
        base = self._filtered(stage=stage, owner_id=owner_id, contact_id=contact_id)
        total = await self.session.scalar(select(func.count()).select_from(base.subquery()))
        rows = await self.session.execute(
            base.order_by(Deal.created_at.desc()).limit(limit).offset(offset)
        )
        return list(rows.scalars().all()), int(total or 0)

    async def stage_history(self, deal_id: uuid.UUID) -> list[DealStageHistory]:
        result = await self.session.execute(
            select(DealStageHistory)
            .where(DealStageHistory.deal_id == deal_id)
            .order_by(DealStageHistory.changed_at.asc())
        )
        return list(result.scalars().all())
