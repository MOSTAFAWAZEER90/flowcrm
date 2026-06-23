from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.enums import ContactStatus, LeadChannel
from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    model = Contact

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_active(self, contact_id: uuid.UUID) -> Contact | None:
        result = await self.session.execute(
            select(Contact).where(Contact.id == contact_id, Contact.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def find_by_external_id(self, external_id: str) -> Contact | None:
        """Match on external_refs->>'external_id' for idempotent upsert."""
        result = await self.session.execute(
            select(Contact).where(
                Contact.external_refs["external_id"].astext == external_id
            )
        )
        return result.scalars().first()

    def _filtered(
        self,
        *,
        search: str | None,
        status: ContactStatus | None,
        source: LeadChannel | None,
        assigned_to: uuid.UUID | None,
        tag: str | None,
    ) -> Select:
        stmt = select(Contact).where(Contact.deleted_at.is_(None))
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                or_(Contact.full_name.ilike(like), Contact.email.ilike(like))
            )
        if status is not None:
            stmt = stmt.where(Contact.status == status)
        if source is not None:
            stmt = stmt.where(Contact.source == source)
        if assigned_to is not None:
            stmt = stmt.where(Contact.assigned_to == assigned_to)
        if tag:
            stmt = stmt.where(Contact.tags.any(tag))  # tag membership via ANY
        return stmt

    async def search(
        self,
        *,
        search: str | None = None,
        status: ContactStatus | None = None,
        source: LeadChannel | None = None,
        assigned_to: uuid.UUID | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Contact], int]:
        base = self._filtered(
            search=search, status=status, source=source, assigned_to=assigned_to, tag=tag
        )
        total = await self.session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        rows = await self.session.execute(
            base.order_by(Contact.created_at.desc()).limit(limit).offset(offset)
        )
        return list(rows.scalars().all()), int(total or 0)
