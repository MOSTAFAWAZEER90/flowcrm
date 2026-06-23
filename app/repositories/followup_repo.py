from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.followup_sequence import FollowupSequence
from app.repositories.base import BaseRepository


class FollowupRepository(BaseRepository[FollowupSequence]):
    model = FollowupSequence

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def active_for_contact(self, contact_id: uuid.UUID) -> FollowupSequence | None:
        result = await self.session.execute(
            select(FollowupSequence).where(
                FollowupSequence.contact_id == contact_id,
                FollowupSequence.is_active.is_(True),
            )
        )
        return result.scalars().first()

    async def due(self, now: datetime, *, limit: int = 100) -> list[FollowupSequence]:
        result = await self.session.execute(
            select(FollowupSequence)
            .where(
                FollowupSequence.is_active.is_(True),
                FollowupSequence.next_run_at.is_not(None),
                FollowupSequence.next_run_at <= now,
            )
            .order_by(FollowupSequence.next_run_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
