from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentPrincipal, DBSession
from app.models.enums import TaskStatus
from app.schemas.common import Page
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=Page[TaskOut])
async def list_tasks(
    session: DBSession,
    principal: CurrentPrincipal,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    assigned_to: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    deal_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[TaskOut]:
    service = TaskService(session, principal)
    items, total = await service.list(
        status=status_filter,
        assigned_to=assigned_to,
        contact_id=contact_id,
        deal_id=deal_id,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[TaskOut.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate, session: DBSession, principal: CurrentPrincipal
) -> TaskOut:
    service = TaskService(session, principal)
    task = await service.create(payload)
    return TaskOut.model_validate(task)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    session: DBSession,
    principal: CurrentPrincipal,
) -> TaskOut:
    service = TaskService(session, principal)
    task = await service.update(task_id, payload)
    return TaskOut.model_validate(task)
