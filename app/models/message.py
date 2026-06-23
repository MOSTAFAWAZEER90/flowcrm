from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.models.enums import AIIntent, MessageDirection, pg_enum


class Message(UUIDPKMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("org_id", "external_id", name="uq_message_external"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[MessageDirection] = mapped_column(
        pg_enum(MessageDirection, "message_direction"), nullable=False
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_intent: Mapped[AIIntent | None] = mapped_column(pg_enum(AIIntent, "ai_intent"), nullable=True)
    ai_sentiment: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
