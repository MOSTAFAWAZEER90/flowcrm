from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal
from app.core.errors import NotFoundError
from app.models.deal import Deal
from app.models.deal_stage_history import DealStageHistory
from app.repositories.deal_repo import DealRepository
from app.schemas.deal import DealCreate, DealUpdate


class DealService:
    """Stage changes (and history rows) are handled by DB triggers
    (``deal_stamp_stage`` / ``deal_log_stage``); the service just persists the
    new stage value."""

    def __init__(self, session: AsyncSession, principal: Principal):
        self.session = session
        self.principal = principal
        self.repo = DealRepository(session)

    async def get(self, deal_id: uuid.UUID) -> Deal:
        deal = await self.repo.get(deal_id)
        if deal is None:
            raise NotFoundError("Deal not found")
        return deal

    async def create(self, payload: DealCreate) -> Deal:
        deal = Deal(
            org_id=self.principal.org_id,
            contact_id=payload.contact_id,
            title=payload.title,
            stage=payload.stage,
            value=payload.value,
            currency=payload.currency,
            owner_id=payload.owner_id or self.principal.user_id,
            probability=payload.probability,
            expected_close=payload.expected_close,
        )
        deal = await self.repo.add(deal)
        await self.session.refresh(deal)  # pick up trigger-set stage_changed_at
        return deal

    async def update(self, deal_id: uuid.UUID, payload: DealUpdate) -> Deal:
        deal = await self.get(deal_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(deal, key, value)
        await self.session.flush()
        await self.session.refresh(deal)  # pick up trigger-set stage/closed timestamps
        return deal

    async def list(self, **filters) -> tuple[list[Deal], int]:
        return await self.repo.search(**filters)

    async def stage_history(self, deal_id: uuid.UUID) -> list[DealStageHistory]:
        await self.get(deal_id)
        return await self.repo.stage_history(deal_id)
