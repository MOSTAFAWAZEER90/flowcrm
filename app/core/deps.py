"""FastAPI dependencies: auth principal, RLS-scoped DB session, RBAC guards."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.security import ACCESS_TOKEN, JWTError, decode_token
from app.models.enums import UserRole

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    """Authenticated identity decoded from the JWT."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: UserRole
    email: str


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #
async def get_system_session() -> AsyncGenerator[AsyncSession, None]:
    """Unscoped session running as the owner role (bypasses RLS).

    Used ONLY for auth/bootstrap flows (register, login) that must read across
    tenants before an org context exists. Commits on success, rolls back on error.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    """Decode the bearer token into a Principal."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != ACCESS_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    try:
        return Principal(
            user_id=uuid.UUID(payload["sub"]),
            org_id=uuid.UUID(payload["org_id"]),
            role=UserRole(payload["role"]),
            email=payload["email"],
        )
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token claims")


async def get_db(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> AsyncGenerator[AsyncSession, None]:
    """RLS-scoped, request-lifetime session (unit-of-work).

    Switches into the non-bypass ``DB_APP_ROLE`` (e.g. ``authenticated`` on
    Supabase, ``flowcrm_app`` locally) so RLS applies even when the login role
    has BYPASSRLS, then pins the tenant + actor for the transaction. All work
    happens in one transaction committed here on success — services only flush.
    """
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text(f'SET LOCAL ROLE "{settings.db_app_role}"'))
            await session.execute(
                text("SELECT set_config('app.current_org', :v, true)"),
                {"v": str(principal.org_id)},
            )
            await session.execute(
                text("SELECT set_config('app.current_user_id', :v, true)"),
                {"v": str(principal.user_id)},
            )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Convenience type aliases for routers.
DBSession = Annotated[AsyncSession, Depends(get_db)]
SystemSession = Annotated[AsyncSession, Depends(get_system_session)]
CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


# --------------------------------------------------------------------------- #
# RBAC
# --------------------------------------------------------------------------- #
def require_roles(*roles: UserRole):
    """Build a dependency that allows only the given roles."""
    allowed: Sequence[UserRole] = roles

    async def _guard(principal: CurrentPrincipal) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(r.value for r in allowed)}",
            )
        return principal

    return _guard


# Common role bundles.
require_admin = require_roles(UserRole.admin)
require_manager = require_roles(UserRole.admin, UserRole.manager)
require_staff = require_roles(
    UserRole.admin, UserRole.manager, UserRole.sales_rep, UserRole.support
)
