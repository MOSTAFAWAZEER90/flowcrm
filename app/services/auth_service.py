"""Authentication & org/user provisioning.

These flows must read/write across tenants before an org context exists, so they
opt out of RLS for their transaction via ``app.bypass_rls='on'`` (transaction-
local, set by ``_enable_bypass``). This is only ever called from trusted auth
code paths.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.errors import AuthError, ConflictError, NotFoundError
from app.core.security import INVITE_TOKEN, JWTError, decode_token
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from app.repositories.organization_repo import OrganizationRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    InviteAcceptRequest,
    InviteRequest,
    LoginRequest,
    RegisterRequest,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


async def _enable_bypass(session: AsyncSession) -> None:
    """Opt this transaction out of RLS (cross-tenant auth lookups)."""
    await session.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "org"


def _token_for(user: User) -> tuple[str, int]:
    token = security.create_token(
        user_id=user.id,
        org_id=user.org_id,
        role=user.role.value,
        email=user.email,
    )
    return token, settings.jwt_access_ttl_minutes * 60


async def register(session: AsyncSession, payload: RegisterRequest) -> tuple[User, str, int]:
    await _enable_bypass(session)
    org_repo = OrganizationRepository(session)
    user_repo = UserRepository(session)

    slug = _slugify(payload.org_slug or payload.org_name)
    if await org_repo.get_by_slug(slug):
        # Disambiguate with a short suffix rather than failing outright.
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    org = Organization(name=payload.org_name, slug=slug, plan="free", status="active")
    await org_repo.add(org)

    user = User(
        org_id=org.id,
        email=str(payload.email).lower(),
        full_name=payload.full_name,
        role=UserRole.admin,
        auth_uid=security.hash_password(payload.password),
        is_active=True,
    )
    await user_repo.add(user)

    token, expires_in = _token_for(user)
    return user, token, expires_in


async def authenticate(session: AsyncSession, payload: LoginRequest) -> tuple[User, str, int]:
    await _enable_bypass(session)
    user_repo = UserRepository(session)
    user = await user_repo.get_by_email_global(str(payload.email).lower())
    if user is None or not security.verify_password(payload.password, user.auth_uid):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("User account is disabled")

    user.last_seen_at = datetime.now(timezone.utc)
    await session.flush()

    token, expires_in = _token_for(user)
    return user, token, expires_in


async def create_invite(org_id: uuid.UUID, payload: InviteRequest) -> tuple[str, int]:
    from datetime import timedelta

    token = security.create_token(
        user_id="invite",
        org_id=org_id,
        role=payload.role.value,
        email=str(payload.email).lower(),
        token_type=INVITE_TOKEN,
        expires_delta=timedelta(hours=settings.jwt_invite_ttl_hours),
        extra={"full_name": payload.full_name},
    )
    return token, settings.jwt_invite_ttl_hours


async def accept_invite(session: AsyncSession, payload: InviteAcceptRequest) -> tuple[User, str, int]:
    await _enable_bypass(session)
    try:
        claims = decode_token(payload.token)
    except JWTError:
        raise AuthError("Invalid or expired invite token")
    if claims.get("type") != INVITE_TOKEN:
        raise AuthError("Not an invite token")

    org_id = uuid.UUID(claims["org_id"])
    email = str(claims["email"]).lower()
    role = UserRole(claims["role"])

    org_repo = OrganizationRepository(session)
    if await org_repo.get(org_id) is None:
        raise NotFoundError("Organization no longer exists")

    user_repo = UserRepository(session)
    if await user_repo.get_by_email_in_org(org_id, email):
        raise ConflictError("A user with this email already exists in the organization")

    user = User(
        org_id=org_id,
        email=email,
        full_name=claims.get("full_name", email.split("@")[0]),
        role=role,
        auth_uid=security.hash_password(payload.password),
        is_active=True,
    )
    await user_repo.add(user)

    token, expires_in = _token_for(user)
    return user, token, expires_in
