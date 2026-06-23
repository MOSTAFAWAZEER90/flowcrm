"""Test fixtures.

Pure-logic tests (scoring, cadence) run anywhere. DB-backed tests (upsert, RLS)
require a reachable PostgreSQL — point TEST_DATABASE_URL at it (defaults to the
docker-compose database). If migrations cannot be applied, those tests skip.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

# --- Configure environment BEFORE importing the app ------------------------- #
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://flowcrm:flowcrm@localhost:5432/flowcrm",
    ),
)
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALG", "HS256")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "")  # force heuristic fallback in tests
os.environ.setdefault("DB_APP_ROLE", "flowcrm_app")
os.environ.setdefault("DB_STATEMENT_CACHE_SIZE", "0")
os.environ.setdefault("ENVIRONMENT", "test")
# Use NullPool so asyncpg connections aren't reused across per-test event loops.
os.environ.setdefault("DB_DISABLE_POOL", "1")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def apply_migrations() -> None:
    """Run alembic migrations once in a subprocess (own event loop)."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env={**os.environ},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(
            "Database not available / migrations failed; skipping DB-backed tests.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


@pytest_asyncio.fixture
async def org_factory(apply_migrations):
    """Return an async factory that registers a fresh org + admin user."""
    from app.core.db import AsyncSessionLocal
    from app.schemas.auth import RegisterRequest
    from app.services import auth_service

    async def _make() -> tuple[uuid.UUID, uuid.UUID]:
        suffix = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            user, _, _ = await auth_service.register(
                session,
                RegisterRequest(
                    org_name=f"Org {suffix}",
                    full_name=f"Admin {suffix}",
                    email=f"admin-{suffix}@example.com",
                    password="password123",
                ),
            )
            await session.commit()
            return user.org_id, user.id

    return _make


@pytest.fixture
def scoped_session(apply_migrations):
    """Expose the tenant-scoped (RLS-enforcing) session context manager."""
    from app.workers.queue import scoped_worker_session

    return scoped_worker_session
