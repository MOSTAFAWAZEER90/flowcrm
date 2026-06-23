"""ARQ connection helpers and a tenant-scoped worker session."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import AsyncSessionLocal


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def get_pool() -> ArqRedis:
    return await create_pool(redis_settings())


@asynccontextmanager
async def scoped_worker_session(
    org_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> AsyncGenerator[AsyncSession, None]:
    """A worker session that enforces RLS just like the request path."""
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text(f'SET LOCAL ROLE "{settings.db_app_role}"'))
            await session.execute(
                text("SELECT set_config('app.current_org', :v, true)"), {"v": str(org_id)}
            )
            if user_id is not None:
                await session.execute(
                    text("SELECT set_config('app.current_user_id', :v, true)"),
                    {"v": str(user_id)},
                )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
