"""Declarative base and shared column mixins."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base.

    ``eager_defaults`` makes server-generated values (created_at/updated_at via
    defaults + triggers) be fetched with RETURNING on INSERT/UPDATE, instead of
    being expired and lazily reloaded — which would break under async sessions.
    """

    __mapper_args__ = {"eager_defaults": True}


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # ORM-side; a DB trigger also covers raw SQL writes
        nullable=False,
    )


class OrgScopedMixin:
    """Tenant ownership column. RLS policies key off this."""

    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
