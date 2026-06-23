from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal
from app.core.errors import NotFoundError
from app.models.conversation import Conversation
from app.models.enums import MessageDirection
from app.models.message import Message
from app.repositories.conversation_repo import ConversationRepository, MessageRepository
from app.schemas.conversation import OutboundMessageCreate


class ConversationService:
    def __init__(self, session: AsyncSession, principal: Principal):
        self.session = session
        self.principal = principal
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)

    async def list(self, *, open_only: bool, limit: int, offset: int) -> list[Conversation]:
        return await self.conversations.list_conversations(
            open_only=open_only, limit=limit, offset=offset
        )

    async def get(self, conversation_id: uuid.UUID) -> Conversation:
        conv = await self.conversations.get(conversation_id)
        if conv is None:
            raise NotFoundError("Conversation not found")
        return conv

    async def list_messages(self, conversation_id: uuid.UUID) -> list[Message]:
        await self.get(conversation_id)  # ensures existence / tenant access
        return await self.messages.list_for_conversation(conversation_id)

    async def send_outbound(
        self, conversation_id: uuid.UUID, payload: OutboundMessageCreate
    ) -> Message:
        conv = await self.get(conversation_id)
        now = datetime.now(timezone.utc)
        message = Message(
            org_id=self.principal.org_id,
            conversation_id=conv.id,
            direction=MessageDirection.outbound,
            sender_user_id=self.principal.user_id,
            body=payload.body,
            attachments=payload.attachments,
            external_id=payload.external_id,
        )
        self.session.add(message)
        conv.last_message_at = now
        conv.unread_count = 0  # outbound clears unread
        await self.session.flush()
        return message
