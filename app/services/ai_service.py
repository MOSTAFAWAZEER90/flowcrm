"""AI utilities backed by OpenAI (gpt-4o-mini, JSON mode).

If ``OPENAI_API_KEY`` is unset or a call fails, every function degrades to a
deterministic local heuristic so the application stays fully functional in dev
and tests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import AIIntent

log = get_logger("ai")

CLASSIFY_SYSTEM_PROMPT = (
    "You are a CRM lead-qualification engine. Return ONLY JSON with keys: "
    "intent, buying_signal, lead_score (0-100), summary (<=20 words), "
    "suggested_reply, next_action."
)

_VALID_INTENTS = {i.value for i in AIIntent}


@dataclass(frozen=True)
class Classification:
    intent: AIIntent
    buying_signal: bool
    ai_base_score: int
    summary: str
    suggested_reply: str
    next_action: str


_client = None


def _get_client():
    global _client
    if not settings.openai_api_key:
        return None
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout)
    return _client


# --------------------------------------------------------------------------- #
# Heuristic fallbacks
# --------------------------------------------------------------------------- #
def _heuristic_classify(text: str) -> Classification:
    t = (text or "").lower()

    def has(*words: str) -> bool:
        return any(w in t for w in words)

    if has("not interested", "unsubscribe", "stop", "remove me", "no thanks"):
        intent, score, signal = AIIntent.not_interested, 10, False
    elif has("buy", "purchase", "ready to", "sign up", "let's do it", "take my money"):
        intent, score, signal = AIIntent.ready_to_buy, 90, True
    elif has("price", "pricing", "cost", "quote", "how much"):
        intent, score, signal = AIIntent.pricing, 75, True
    elif has("book", "appointment", "schedule", "demo", "meeting", "call"):
        intent, score, signal = AIIntent.booking, 70, True
    elif has("refund", "complaint", "angry", "terrible", "worst"):
        intent, score, signal = AIIntent.complaint, 30, False
    elif has("help", "issue", "problem", "support", "broken", "error"):
        intent, score, signal = AIIntent.support, 45, False
    elif has("free money", "lottery", "click here", "viagra"):
        intent, score, signal = AIIntent.spam, 0, False
    else:
        intent, score, signal = AIIntent.inquiry, 50, False

    snippet = (text or "").strip().replace("\n", " ")
    summary = (snippet[:97] + "...") if len(snippet) > 100 else (snippet or "No content")
    return Classification(
        intent=intent,
        buying_signal=signal,
        ai_base_score=score,
        summary=summary,
        suggested_reply="Thanks for reaching out! How can we help you today?",
        next_action="Review and respond to the lead.",
    )


def _coerce_classification(data: dict) -> Classification:
    raw_intent = str(data.get("intent", "other")).lower().strip()
    intent = AIIntent(raw_intent) if raw_intent in _VALID_INTENTS else AIIntent.other
    try:
        score = int(round(float(data.get("lead_score", 50))))
    except (TypeError, ValueError):
        score = 50
    score = max(0, min(100, score))
    return Classification(
        intent=intent,
        buying_signal=bool(data.get("buying_signal", False)),
        ai_base_score=score,
        summary=str(data.get("summary", ""))[:280],
        suggested_reply=str(data.get("suggested_reply", "")),
        next_action=str(data.get("next_action", "")),
    )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
async def classify(text: str) -> Classification:
    client = _get_client()
    if client is None:
        return _heuristic_classify(text)
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        return _coerce_classification(json.loads(content))
    except Exception as exc:  # network / parsing / rate-limit
        log.warning("ai_classify_fallback", error=str(exc))
        return _heuristic_classify(text)


def _transcript(messages: list[tuple[str, str | None]]) -> str:
    lines = []
    for direction, body in messages:
        who = "Customer" if direction == "inbound" else "Agent"
        lines.append(f"{who}: {body or ''}")
    return "\n".join(lines)


async def summarize(messages: list[tuple[str, str | None]]) -> str:
    if not messages:
        return "No messages in this conversation yet."
    client = _get_client()
    transcript = _transcript(messages)
    if client is None:
        last = messages[-1][1] or ""
        return f"{len(messages)} messages. Latest: {last[:160]}"
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "Summarize this CRM conversation in 2-3 sentences, "
                    "highlighting intent and any next step.",
                },
                {"role": "user", "content": transcript},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        log.warning("ai_summarize_fallback", error=str(exc))
        last = messages[-1][1] or ""
        return f"{len(messages)} messages. Latest: {last[:160]}"


async def draft_reply(messages: list[tuple[str, str | None]], tone: str) -> str:
    client = _get_client()
    if client is None:
        return (
            "Thank you for your message! I'd be happy to help. "
            "Could you share a bit more about what you're looking for?"
        )
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.5,
            messages=[
                {
                    "role": "system",
                    "content": f"You are a helpful sales/support agent. Draft the next "
                    f"reply in a {tone} tone. Reply with the message text only.",
                },
                {"role": "user", "content": _transcript(messages)},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        log.warning("ai_reply_fallback", error=str(exc))
        return "Thanks for reaching out — let me look into this and get right back to you."
