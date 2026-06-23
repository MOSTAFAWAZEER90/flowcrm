from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentPrincipal, DBSession
from app.models.enums import PipelineStage
from app.schemas.common import Page
from app.schemas.deal import DealCreate, DealOut, DealUpdate, StageHistoryOut
from app.services.deal_service import DealService

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("", response_model=Page[DealOut])
async def list_deals(
    session: DBSession,
    principal: CurrentPrincipal,
    stage: PipelineStage | None = None,
    owner_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[DealOut]:
    service = DealService(session, principal)
    items, total = await service.list(
        stage=stage, owner_id=owner_id, contact_id=contact_id, limit=limit, offset=offset
    )
    return Page(
        items=[DealOut.model_validate(d) for d in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=DealOut, status_code=status.HTTP_201_CREATED)
async def create_deal(
    payload: DealCreate, session: DBSession, principal: CurrentPrincipal
) -> DealOut:
    service = DealService(session, principal)
    deal = await service.create(payload)
    return DealOut.model_validate(deal)


@router.patch("/{deal_id}", response_model=DealOut)
async def update_deal(
    deal_id: uuid.UUID,
    payload: DealUpdate,
    session: DBSession,
    principal: CurrentPrincipal,
) -> DealOut:
    """Updating ``stage`` auto-logs a deal_stage_history row via DB trigger."""
    service = DealService(session, principal)
    deal = await service.update(deal_id, payload)
    return DealOut.model_validate(deal)


@router.get("/{deal_id}/history", response_model=list[StageHistoryOut])
async def deal_history(
    deal_id: uuid.UUID, session: DBSession, principal: CurrentPrincipal
) -> list[StageHistoryOut]:
    service = DealService(session, principal)
    history = await service.stage_history(deal_id)
    return [StageHistoryOut.model_validate(h) for h in history]
