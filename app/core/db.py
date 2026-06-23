"""Async SQLAlchemy engine and session factory."""
from __future__ import annotations

import os
import ssl

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


def build_connect_args() -> dict:
    """asyncpg connect args shared by the app engine and Alembic."""
    args: dict = {}
    # Disable asyncpg's prepared-statement cache behind a transaction pooler
    # (PgBouncer / Supabase / Neon), which doesn't support it.
    if "asyncpg" in settings.database_url and settings.db_statement_cache_size == 0:
        args["statement_cache_size"] = 0
    # Cloud Postgres (Supabase / Neon) requires TLS. We use an unverified
    # context for setup convenience; tighten (verify-full + CA) in production.
    if settings.db_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        args["ssl"] = ctx
    return args


# Under pytest, use NullPool so asyncpg connections are never reused across the
# per-test event loops (which otherwise raises "Event loop is closed").
if os.getenv("DB_DISABLE_POOL") == "1":
    engine: AsyncEngine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        poolclass=NullPool,
        connect_args=build_connect_args(),
    )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        connect_args=build_connect_args(),
    )

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def dispose_engine() -> None:
    await engine.dispose()
