from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, status

from app.core.deps import SystemSession
from app.core.logging import get_logger
from app.services import webhook_service

log = get_logger("webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{source}")
async def receive_webhook(source: str, request: Request, session: SystemSession) -> dict:
    if source not in webhook_service.VALID_SOURCES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown webhook source")

    body = await request.body()
    if not webhook_service.verify_signature(source, body, dict(request.headers)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature"
        )

    try:
        raw = json.loads(body) if body else {}
        if not isinstance(raw, dict):
            raw = {"_payload": raw}
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Body is not valid JSON"
        )

    external_id = webhook_service.extract_external_id(source, raw, body)
    event, is_new = await webhook_service.record_event(
        session, source=source, external_id=external_id, raw=raw
    )
    # Persist before enqueuing so the worker can read the row.
    await session.commit()

    if not is_new or event is None:
        log.info("webhook_duplicate", source=source, external_id=external_id)
        return {"status": "duplicate", "external_id": external_id}

    # Enqueue for async processing; never block the 200 on Redis availability.
    arq = getattr(request.app.state, "arq", None)
    if arq is not None:
        try:
            await arq.enqueue_job("process_webhook", str(event.id))
        except Exception as exc:  # Redis down etc. — event is stored, retried later
            log.warning("webhook_enqueue_failed", error=str(exc), event_id=str(event.id))

    return {"status": "accepted", "external_id": external_id, "event_id": str(event.id)}
