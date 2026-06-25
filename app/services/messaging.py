"""Outbound messaging — WhatsApp (to customers) and Telegram (to the owner).

Shared by reminders (#2), conversation summaries (#4), and Facebook DM follow-up
(#6). Each function no-ops (returns False) if its credentials aren't configured,
so the app never crashes when a channel isn't set up yet.
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("messaging")


async def send_whatsapp(to_phone: str | None, text: str) -> bool:
    """Send a WhatsApp text via the Meta Cloud API Graph endpoint."""
    if not (settings.whatsapp_access_token and settings.whatsapp_phone_number_id):
        log.warning("whatsapp_send_skipped", reason="missing token/phone_number_id")
        return False
    if not to_phone:
        return False
    url = (
        f"https://graph.facebook.com/{settings.whatsapp_api_version}"
        f"/{settings.whatsapp_phone_number_id}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code >= 300:
                log.warning("whatsapp_send_failed", status=r.status_code, body=r.text[:300])
                return False
            return True
    except Exception as exc:
        log.warning("whatsapp_send_error", error=str(exc))
        return False


async def _fb_post(path: str, body: dict) -> bool:
    token = settings.facebook_page_access_token
    if not token:
        log.warning("facebook_send_skipped", reason="missing page access token")
        return False
    url = f"https://graph.facebook.com/{settings.whatsapp_api_version}/{path}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json=body, params={"access_token": token})
            if r.status_code >= 300:
                log.warning("facebook_send_failed", status=r.status_code, body=r.text[:300])
                return False
            return True
    except Exception as exc:
        log.warning("facebook_send_error", error=str(exc))
        return False


async def fb_reply_to_comment(comment_id: str, text: str) -> bool:
    """Public reply under a Facebook comment."""
    return await _fb_post(f"{comment_id}/comments", {"message": text})


async def fb_private_reply(comment_id: str, text: str) -> bool:
    """Open a private message (DM) to the person who commented."""
    return await _fb_post(f"{comment_id}/private_replies", {"message": text})


async def send_telegram(text: str) -> bool:
    """Send a message to the owner's Telegram chat."""
    if not (settings.telegram_bot_token and settings.owner_telegram_chat_id):
        log.warning("telegram_send_skipped", reason="missing bot token / chat id")
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                url, json={"chat_id": settings.owner_telegram_chat_id, "text": text}
            )
            return r.status_code < 300
    except Exception as exc:
        log.warning("telegram_send_error", error=str(exc))
        return False
