"""AI utilities backed by OpenAI (gpt-4o-mini, JSON mode).

The assistant is instructed to behave as a real human sales representative — it
must never reveal or hint that it is an AI/bot, and always replies in the
customer's own language/dialect. If ``OPENAI_API_KEY`` is unset or a call fails,
every function degrades to a deterministic (human-sounding) local heuristic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import AIIntent

log = get_logger("ai")


def _persona() -> str:
    """System prompt that makes the model behave as a real human sales rep."""
    return (
        f"You are {settings.ai_agent_name}, a real human sales representative at "
        f"{settings.ai_company_name}. You are a PERSON, not an AI. NEVER say, reveal, or hint "
        f"in any way that you are an AI, bot, assistant, or automated system — under any "
        f"circumstance. Talk like a warm, friendly human texting a customer: natural, short, "
        f"personable, light emojis when they fit. ALWAYS reply in the SAME language and dialect "
        f"the customer used — if they wrote Arabic, reply in natural Egyptian Arabic. Never use "
        f"robotic, overly formal, or templated phrasing, and never add disclaimers."
    )


CLASSIFY_SYSTEM_PROMPT = (
    "You are a CRM lead-qualification engine. Analyze the customer's message and return ONLY "
    "JSON with keys: intent (one of: inquiry, pricing, booking, support, complaint, spam, "
    "ready_to_buy, not_interested, other), buying_signal (true/false), lead_score (0-100), "
    "summary (<=20 words, internal), suggested_reply, next_action. "
    "For 'suggested_reply': write it EXACTLY as a real human salesperson would text back — "
    "warm and natural, in the SAME language/dialect as the customer (Egyptian Arabic if they "
    "wrote Arabic). It must NEVER reveal or hint at being an AI/bot and must avoid robotic or "
    "templated wording."
)

SUMMARY_SYSTEM_PROMPT = (
    "You are preparing a short internal summary of a sales conversation FOR THE BUSINESS OWNER "
    "(not the customer). Write it in Arabic, concise and professional, with these labeled "
    "lines exactly:\n"
    "• احتياج العميل:\n"
    "• المنتجات/الخدمات اللي اتناقشت:\n"
    "• مستوى اهتمام العميل (عالي/متوسط/ضعيف):\n"
    "• الخطوة الجاية المقترحة:"
)

_VALID_INTENTS = {i.value for i in AIIntent}

# Human, warm fallback replies (Egyptian Arabic) used when no OpenAI key is set.
_HEURISTIC_REPLIES: dict[AIIntent, str] = {
    AIIntent.pricing: "أهلاً بيك 🙏 قولّي محتاج إيه بالظبط وأبعتلك التفاصيل والأسعار حالًا 👌",
    AIIntent.ready_to_buy: "تمام يا فندم! 🙌 ابعتلي بياناتك وأنا أكمّل معاك الطلب على طول.",
    AIIntent.booking: "تمام! إمتى يكون الوقت المناسب ليك ونظبّط الميعاد؟ 📅",
    AIIntent.support: "معلش على اللي حصل 🙏 قولّي المشكلة بالظبط وأظبّطهالك حالًا.",
    AIIntent.complaint: "أنا آسف جدًا على ده 🙏 طمّني على التفاصيل وأنا هحلّهالك بنفسي.",
    AIIntent.inquiry: "أهلاً بيك! 🙏 تحت أمرك، قولّي محتاج تعرف إيه وأساعدك على طول 😊",
    AIIntent.not_interested: "تمام، متشكرين لوقتك 🌸 ولو احتجت أي حاجة في أي وقت أنا موجود.",
    AIIntent.other: "أهلاً بيك! 🙏 قولّي أقدر أساعدك بإيه؟",
    AIIntent.spam: "",
}


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
# Heuristic fallbacks (human-sounding)
# --------------------------------------------------------------------------- #
def _heuristic_classify(text: str) -> Classification:
    t = (text or "").lower()

    def has(*words: str) -> bool:
        return any(w in t for w in words)

    # English + common Arabic keywords.
    if has("not interested", "unsubscribe", "stop", "مش مهتم", "لا شكرا", "خلاص"):
        intent, score, signal = AIIntent.not_interested, 10, False
    elif has("buy", "purchase", "ready to", "sign up", "اشتري", "هشتري", "عايز اطلب", "تمام هاخده"):
        intent, score, signal = AIIntent.ready_to_buy, 90, True
    elif has("price", "pricing", "cost", "quote", "how much", "سعر", "بكام", "كام", "الاسعار", "تمن"):
        intent, score, signal = AIIntent.pricing, 75, True
    elif has("book", "appointment", "schedule", "demo", "meeting", "ميعاد", "حجز", "موعد"):
        intent, score, signal = AIIntent.booking, 70, True
    elif has("refund", "complaint", "angry", "terrible", "شكوى", "وحش", "زعلان", "مرتجع"):
        intent, score, signal = AIIntent.complaint, 30, False
    elif has("help", "issue", "problem", "support", "مشكلة", "مساعدة", "عطلان", "مش شغال"):
        intent, score, signal = AIIntent.support, 45, False
    elif has("free money", "lottery", "click here", "viagra"):
        intent, score, signal = AIIntent.spam, 0, False
    else:
        intent, score, signal = AIIntent.inquiry, 50, False

    snippet = (text or "").strip().replace("\n", " ")
    summary = (snippet[:97] + "...") if len(snippet) > 100 else (snippet or "بدون محتوى")
    return Classification(
        intent=intent,
        buying_signal=signal,
        ai_base_score=score,
        summary=summary,
        suggested_reply=_HEURISTIC_REPLIES.get(intent, _HEURISTIC_REPLIES[AIIntent.other]),
        next_action="تواصل مع العميل ورُد عليه بسرعة.",
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
            temperature=0.3,
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
    """Structured Arabic summary for the business owner (feature #4)."""
    if not messages:
        return "لسه مفيش رسائل في المحادثة دي."
    client = _get_client()
    transcript = _transcript(messages)
    if client is None:
        inbound = [b for d, b in messages if d == "inbound" and b]
        last = inbound[-1] if inbound else (messages[-1][1] or "")
        return (
            "• احتياج العميل: " + (last[:140] if last else "غير واضح") + "\n"
            "• المنتجات/الخدمات اللي اتناقشت: غير محدّدة\n"
            "• مستوى اهتمام العميل: متوسط\n"
            "• الخطوة الجاية المقترحة: التواصل مع العميل ومتابعة الطلب\n"
            f"(عدد الرسائل: {len(messages)})"
        )
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        log.warning("ai_summarize_fallback", error=str(exc))
        last = messages[-1][1] or ""
        return f"ملخص سريع: {len(messages)} رسالة. آخر رسالة: {last[:160]}"


async def draft_reply(messages: list[tuple[str, str | None]], tone: str) -> str:
    client = _get_client()
    if client is None:
        last = next((b for d, b in reversed(messages) if d == "inbound" and b), "")
        intent = _heuristic_classify(last).intent
        return _HEURISTIC_REPLIES.get(intent) or _HEURISTIC_REPLIES[AIIntent.other]
    try:
        system = _persona()
        if tone:
            system += f" The desired tone is: {tone}."
        system += " Reply with ONLY the message text to send the customer — nothing else."
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.7,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": _transcript(messages)},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        log.warning("ai_reply_fallback", error=str(exc))
        return "أهلاً بيك! 🙏 وصلتني رسالتك، قولّي تفاصيل أكتر عن اللي محتاجه وأساعدك على طول 👌"
