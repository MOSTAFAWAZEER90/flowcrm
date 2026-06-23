from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    def _filtered(
        self,
        *,
        status: TaskStatus | None,
        assigned_to: uuid.UUID | None,
        contact_id: uuid.UUID | None,
        deal_id: uuid.UUID | None,
    ) -> Select:
        stmt = select(Task)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if assigned_to is not None:
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if contact_id is not None:
            stmt = stmt.where(Task.contact_id == contact_id)
        if deal_id is not None:
            stmt = stmt.where(Task.deal_id == deal_id)
        return stmt

    async def search(
        self,
        *,
        status: TaskStatus | None = None,
        assigned_to: uuid.UUID | None = None,
        contact_id: uuid.UUID | None = None,
        deal_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Task], int]:
        base = self._filtered(
            status=status, assigned_to=assigned_to, contact_id=contact_id, deal_id=deal_id
        )
        total = await self.session.scalar(select(func.count()).select_from(base.subquery()))
        rows = await self.session.execute(
            base.order_by(Task.due_at.asc().nullslast(), Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars().all()), int(total or 0)
