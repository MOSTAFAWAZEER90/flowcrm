from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_conversations(
        self, *, open_only: bool = False, limit: int = 50, offset: int = 0
    ) -> list[Conversation]:
        stmt = select(Conversation)
        if open_only:
            stmt = stmt.where(Conversation.is_open.is_(True))
        stmt = stmt.order_by(Conversation.last_message_at.desc().nullslast())
        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def get_for_contact(self, contact_id: uuid.UUID) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.contact_id == contact_id)
            .order_by(Conversation.created_at.asc())
        )
        return result.scalars().first()


class MessageRepository(BaseRepository[Message]):
    model = Message

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def list_for_conversation(
        self, conversation_id: uuid.UUID, *, limit: int = 200, offset: int = 0
    ) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def has_inbound_since(self, contact_id: uuid.UUID, since) -> bool:
        """True if the contact has any inbound message after ``since`` (used by cadence)."""
        from app.models.conversation import Conversation as Conv

        result = await self.session.execute(
            select(Message.id)
            .join(Conv, Conv.id == Message.conversation_id)
            .where(
                Conv.contact_id == contact_id,
                Message.direction == "inbound",
                Message.created_at > since,
            )
            .limit(1)
        )
        return result.first() is not None
