from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentPrincipal, DBSession
from app.schemas.reminder import ProcessResult, ReminderCreate, ReminderOut
from app.services.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
async def schedule_reminder(
    payload: ReminderCreate, session: DBSession, principal: CurrentPrincipal
) -> ReminderOut:
    """Save a follow-up reminder at the time the customer chose."""
    service = ReminderService(session, principal)
    reminder = await service.schedule(
        payload.external_id, payload.remind_at, payload.message, payload.channel
    )
    return ReminderOut.model_validate(reminder)


@router.get("/due", response_model=list[ReminderOut])
async def due_reminders(session: DBSession, principal: CurrentPrincipal) -> list[ReminderOut]:
    """Reminders whose time has come and are still pending."""
    service = ReminderService(session, principal)
    return [ReminderOut.model_validate(r) for r, _ in await service.due()]


@router.post("/process", response_model=ProcessResult)
async def process_reminders(session: DBSession, principal: CurrentPrincipal) -> ProcessResult:
    """Send all due reminders via WhatsApp and mark them (called by cron/n8n)."""
    service = ReminderService(session, principal)
    return ProcessResult(**await service.process())
