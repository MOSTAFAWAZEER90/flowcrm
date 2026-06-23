"""Password hashing and JWT creation / verification."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN = "access"
INVITE_TOKEN = "invite"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_token(
    *,
    user_id: uuid.UUID | str,
    org_id: uuid.UUID | str,
    role: str,
    email: str,
    token_type: str = ACCESS_TOKEN,
    expires_delta: timedelta | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT carrying tenant + role claims."""
    issued = _now()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "email": email,
        "type": token_type,
        "iat": int(issued.timestamp()),
        "exp": int((issued + expires_delta).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def create_invite_token(*, org_id: uuid.UUID | str, email: str, role: str) -> str:
    return create_token(
        user_id="invite",  # no user yet
        org_id=org_id,
        role=role,
        email=email,
        token_type=INVITE_TOKEN,
        expires_delta=timedelta(hours=settings.jwt_invite_ttl_hours),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises JWTError on any failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])


__all__ = [
    "ACCESS_TOKEN",
    "INVITE_TOKEN",
    "JWTError",
    "create_invite_token",
    "create_token",
    "decode_token",
    "hash_password",
    "verify_password",
]
