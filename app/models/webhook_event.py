from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class WebhookEvent(UUIDPKMixin, TimestampMixin, Base):
    """Inbound webhook envelope. UNIQUE(source, external_id) gives idempotency.

    ``org_id`` is nullable because the owning org is sometimes only resolved
    while processing the event, and is left out of RLS so the public webhook
    endpoint can insert before a tenant context exists.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_webhook_source_external"),
    )

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
