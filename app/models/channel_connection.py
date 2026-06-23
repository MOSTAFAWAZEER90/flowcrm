from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.models.enums import LeadChannel, pg_enum


class ChannelConnection(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "channel_connections"
    __table_args__ = (
        UniqueConstraint("org_id", "channel", "external_id", name="uq_channel_conn"),
    )

    channel: Mapped[LeadChannel] = mapped_column(pg_enum(LeadChannel, "lead_channel"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credentials: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
