from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentPrincipal, DBSession
from app.schemas.conversation import ConversationOut, MessageOut, OutboundMessageCreate
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    session: DBSession,
    principal: CurrentPrincipal,
    open: bool = Query(default=False, description="Only open conversations"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ConversationOut]:
    service = ConversationService(session, principal)
    convs = await service.list(open_only=open, limit=limit, offset=offset)
    return [ConversationOut.model_validate(c) for c in convs]


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: uuid.UUID, session: DBSession, principal: CurrentPrincipal
) -> list[MessageOut]:
    service = ConversationService(session, principal)
    messages = await service.list_messages(conversation_id)
    return [MessageOut.model_validate(m) for m in messages]


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: OutboundMessageCreate,
    session: DBSession,
    principal: CurrentPrincipal,
) -> MessageOut:
    service = ConversationService(session, principal)
    message = await service.send_outbound(conversation_id, payload)
    return MessageOut.model_validate(message)
