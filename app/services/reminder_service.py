"""Customer-chosen follow-up reminders (feature #2).

Flow: the customer picks a time -> schedule() stores a reminder. An external
trigger (n8n / cron) periodically calls process(), which sends every due
reminder via WhatsApp (human-worded, per feature #1) and marks it sent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal
from app.core.errors import NotFoundError
from app.models.contact import Contact
from app.models.reminder import Reminder
from app.repositories.contact_repo import ContactRepository
from app.services import messaging


def _default_message(name: str | None) -> str:
    who = f" يا {name}" if name else ""
    return (
        f"أهلاً{who} 👋 معلش حبيت أطمّن عليك وأكمّل معاك اللي كنا بدأناه — "
        f"لسه العرض موجود، تحب نكمّل؟ 😊"
    )


class ReminderService:
    def __init__(self, session: AsyncSession, principal: Principal):
        self.session = session
        self.principal = principal

    async def schedule(
        self, external_id: str, remind_at: datetime, message: str | None, channel: str = "whatsapp"
    ) -> Reminder:
        contact = await ContactRepository(self.session).find_by_external_id(external_id)
        if contact is None:
            raise NotFoundError(f"No contact with external_id={external_id}")
        reminder = Reminder(
            org_id=self.principal.org_id,
            contact_id=contact.id,
            remind_at=remind_at,
            message=message,
            channel=channel,
            status="pending",
        )
        self.session.add(reminder)
        await self.session.flush()
        return reminder

    async def due(self, *, limit: int = 100) -> list[tuple[Reminder, Contact]]:
        now = datetime.now(timezone.utc)
        rows = await self.session.execute(
            select(Reminder, Contact)
            .join(Contact, Contact.id == Reminder.contact_id)
            .where(Reminder.status == "pending", Reminder.remind_at <= now)
            .order_by(Reminder.remind_at.asc())
            .limit(limit)
        )
        return list(rows.all())

    async def process(self) -> dict:
        """Send all due reminders and mark them. Called by the cron/n8n trigger."""
        due = await self.due()
        sent = failed = 0
        for reminder, contact in due:
            text = reminder.message or _default_message(contact.full_name)
            ok = await messaging.send_whatsapp(contact.phone, text)
            reminder.status = "sent" if ok else "failed"
            reminder.sent_at = datetime.now(timezone.utc) if ok else None
            sent += int(ok)
            failed += int(not ok)
        await self.session.flush()
        return {"processed": len(due), "sent": sent, "failed": failed}
