from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentPrincipal, DBSession
from app.schemas.followup import (
    AdvanceRequest,
    CompleteRequest,
    DueSequenceOut,
    EnrollRequest,
    SequenceOut,
)
from app.services.followup_service import FollowupService

router = APIRouter(prefix="/followup", tags=["followup"])


@router.post("/enroll", response_model=SequenceOut, status_code=status.HTTP_201_CREATED)
async def enroll(
    payload: EnrollRequest, session: DBSession, principal: CurrentPrincipal
) -> SequenceOut:
    service = FollowupService(session, principal)
    seq = await service.enroll(payload.external_id, payload.template)
    return SequenceOut.model_validate(seq, from_attributes=True)


@router.get("/due", response_model=list[DueSequenceOut])
async def due(
    session: DBSession,
    principal: CurrentPrincipal,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DueSequenceOut]:
    """Sequences whose next_run_at has passed, with contact info and whether the
    contact has replied since enrollment (so n8n can stop the sequence)."""
    service = FollowupService(session, principal)
    return await service.due(limit=limit)


@router.post("/advance", response_model=SequenceOut)
async def advance(
    payload: AdvanceRequest, session: DBSession, principal: CurrentPrincipal
) -> SequenceOut:
    service = FollowupService(session, principal)
    seq = await service.advance(payload.sequence_id, payload.sent_step)
    return SequenceOut.model_validate(seq, from_attributes=True)


@router.post("/complete", response_model=SequenceOut)
async def complete(
    payload: CompleteRequest, session: DBSession, principal: CurrentPrincipal
) -> SequenceOut:
    service = FollowupService(session, principal)
    seq = await service.complete(payload.sequence_id, payload.reason)
    return SequenceOut.model_validate(seq, from_attributes=True)
