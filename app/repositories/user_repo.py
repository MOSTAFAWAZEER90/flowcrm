from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_email_global(self, email: str) -> User | None:
        """Cross-tenant email lookup (used by login on the system session)."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def get_by_email_in_org(self, org_id: uuid.UUID, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.org_id == org_id, User.email == email)
        )
        return result.scalar_one_or_none()
