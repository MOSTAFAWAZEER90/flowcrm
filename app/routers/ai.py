from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentPrincipal, DBSession
from app.schemas.ai import (
    ClassifyRequest,
    ClassifyResponse,
    ReplyRequest,
    ReplyResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from app.services import ai_service, messaging
from app.services.conversation_service import ConversationService
from app.services.scoring import is_hot_lead

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/classify", response_model=ClassifyResponse)
async def classify(payload: ClassifyRequest, principal: CurrentPrincipal) -> ClassifyResponse:
    result = await ai_service.classify(payload.text)
    return ClassifyResponse(
        intent=result.intent,
        buying_signal=result.buying_signal,
        lead_score=result.ai_base_score,
        summary=result.summary,
        suggested_reply=result.suggested_reply,
        next_action=result.next_action,
        is_hot_lead=is_hot_lead(result.ai_base_score, result.buying_signal),
    )


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    payload: SummarizeRequest, session: DBSession, principal: CurrentPrincipal
) -> SummarizeResponse:
    service = ConversationService(session, principal)
    messages = await service.list_messages(payload.conversation_id)
    transcript = [(m.direction.value, m.body) for m in messages]
    summary = await ai_service.summarize(transcript)
    return SummarizeResponse(
        conversation_id=payload.conversation_id,
        summary=summary,
        message_count=len(messages),
    )


@router.post("/notify-owner", response_model=SummarizeResponse)
async def notify_owner(
    payload: SummarizeRequest, session: DBSession, principal: CurrentPrincipal
) -> SummarizeResponse:
    """Summarize a conversation and send the summary to the owner (feature #4)."""
    service = ConversationService(session, principal)
    messages = await service.list_messages(payload.conversation_id)
    transcript = [(m.direction.value, m.body) for m in messages]
    summary = await ai_service.summarize(transcript)
    await messaging.send_telegram(f"📋 ملخص محادثة عميل:\n\n{summary}")
    return SummarizeResponse(
        conversation_id=payload.conversation_id, summary=summary, message_count=len(messages)
    )


@router.post("/reply", response_model=ReplyResponse)
async def reply(
    payload: ReplyRequest, session: DBSession, principal: CurrentPrincipal
) -> ReplyResponse:
    service = ConversationService(session, principal)
    messages = await service.list_messages(payload.conversation_id)
    transcript = [(m.direction.value, m.body) for m in messages]
    draft = await ai_service.draft_reply(transcript, payload.tone)
    return ReplyResponse(conversation_id=payload.conversation_id, reply=draft, tone=payload.tone)
