from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal
from app.core.errors import NotFoundError
from app.models.automation_log import AutomationLog
from app.models.followup_sequence import FollowupSequence
from app.repositories.contact_repo import ContactRepository
from app.repositories.conversation_repo import MessageRepository
from app.repositories.followup_repo import FollowupRepository
from app.schemas.followup import DueSequenceOut
from app.services.cadence import MAX_STEP, initial_schedule, schedule_after_send


class FollowupService:
    def __init__(self, session: AsyncSession, principal: Principal):
        self.session = session
        self.principal = principal
        self.repo = FollowupRepository(session)
        self.contacts = ContactRepository(session)
        self.messages = MessageRepository(session)

    async def enroll(self, external_id: str, template: str) -> FollowupSequence:
        contact = await self.contacts.find_by_external_id(external_id)
        if contact is None:
            raise NotFoundError(f"No contact with external_id={external_id}")

        existing = await self.repo.active_for_contact(contact.id)
        if existing is not None:
            return existing  # idempotent: already enrolled

        now = datetime.now(timezone.utc)
        sequence = FollowupSequence(
            org_id=self.principal.org_id,
            contact_id=contact.id,
            template=template,
            current_step=0,
            next_run_at=initial_schedule(now),
            is_active=True,
        )
        await self.repo.add(sequence)
        return sequence

    async def due(self, *, limit: int = 100) -> list[DueSequenceOut]:
        now = datetime.now(timezone.utc)
        sequences = await self.repo.due(now, limit=limit)
        out: list[DueSequenceOut] = []
        for seq in sequences:
            contact = await self.contacts.get(seq.contact_id)
            replied = await self.messages.has_inbound_since(seq.contact_id, seq.created_at)
            out.append(
                DueSequenceOut(
                    sequence_id=seq.id,
                    contact_id=seq.contact_id,
                    template=seq.template,
                    current_step=seq.current_step,
                    next_step=min(seq.current_step + 1, MAX_STEP),
                    next_run_at=seq.next_run_at,
                    contact_replied=replied,
                    contact_name=contact.full_name if contact else "",
                    contact_email=contact.email if contact else None,
                    contact_phone=contact.phone if contact else None,
                )
            )
        return out

    async def advance(self, sequence_id: uuid.UUID, sent_step: int) -> FollowupSequence:
        seq = await self.repo.get(sequence_id)
        if seq is None:
            raise NotFoundError("Follow-up sequence not found")

        decision = schedule_after_send(seq.created_at, sent_step)
        seq.current_step = sent_step
        seq.next_run_at = decision.next_run_at
        seq.is_active = decision.is_active

        self.session.add(
            AutomationLog(
                org_id=self.principal.org_id,
                workflow="followup_advance",
                entity_type="followup_sequence",
                entity_id=seq.id,
                status="ok",
                payload={"sent_step": sent_step, "is_active": decision.is_active},
            )
        )
        await self.session.flush()
        return seq

    async def complete(self, sequence_id: uuid.UUID, reason: str) -> FollowupSequence:
        seq = await self.repo.get(sequence_id)
        if seq is None:
            raise NotFoundError("Follow-up sequence not found")
        seq.is_active = False
        seq.next_run_at = None
        self.session.add(
            AutomationLog(
                org_id=self.principal.org_id,
                workflow="followup_complete",
                entity_type="followup_sequence",
                entity_id=seq.id,
                status="completed",
                payload={"reason": reason},
            )
        )
        await self.session.flush()
        return seq
