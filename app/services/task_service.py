from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal
from app.core.errors import NotFoundError
from app.models.enums import TaskStatus
from app.models.task import Task
from app.repositories.task_repo import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self, session: AsyncSession, principal: Principal):
        self.session = session
        self.principal = principal
        self.repo = TaskRepository(session)

    async def get(self, task_id: uuid.UUID) -> Task:
        task = await self.repo.get(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        return task

    async def create(self, payload: TaskCreate) -> Task:
        due_at = payload.due_at
        if payload.due_in_minutes is not None:
            due_at = datetime.now(timezone.utc) + timedelta(minutes=payload.due_in_minutes)

        task = Task(
            org_id=self.principal.org_id,
            contact_id=payload.contact_id,
            deal_id=payload.deal_id,
            assigned_to=payload.assigned_to or self.principal.user_id,
            title=payload.title,
            description=payload.description,
            due_at=due_at,
            status=TaskStatus.open,
            created_by_ai=payload.created_by_ai,
        )
        return await self.repo.add(task)

    async def update(self, task_id: uuid.UUID, payload: TaskUpdate) -> Task:
        task = await self.get(task_id)
        data = payload.model_dump(exclude_unset=True)
        new_status = data.get("status")
        for key, value in data.items():
            setattr(task, key, value)
        # Stamp / clear completion time when status transitions.
        if new_status == TaskStatus.done and task.completed_at is None:
            task.completed_at = datetime.now(timezone.utc)
        elif new_status in (TaskStatus.open, TaskStatus.cancelled):
            task.completed_at = None
        await self.session.flush()
        return task

    async def list(self, **filters) -> tuple[list[Task], int]:
        return await self.repo.search(**filters)
