from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import AIIntent


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class ClassifyResponse(BaseModel):
    intent: AIIntent
    buying_signal: bool
    lead_score: int = Field(ge=0, le=100)
    summary: str
    suggested_reply: str
    next_action: str
    is_hot_lead: bool


class SummarizeRequest(BaseModel):
    conversation_id: uuid.UUID


class SummarizeResponse(BaseModel):
    conversation_id: uuid.UUID
    summary: str
    message_count: int


class ReplyRequest(BaseModel):
    conversation_id: uuid.UUID
    tone: str = Field(default="professional", max_length=60)


class ReplyResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    tone: str
