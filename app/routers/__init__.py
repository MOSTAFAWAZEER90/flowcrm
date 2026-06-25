"""v1 API router aggregation."""
from __future__ import annotations

from fastapi import APIRouter

from app.routers import (
    ai,
    auth,
    contacts,
    conversations,
    deals,
    followup,
    public,
    reminders,
    reports,
    tasks,
    webhooks,
    whatsapp,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(contacts.router)
api_router.include_router(conversations.router)
api_router.include_router(deals.router)
api_router.include_router(tasks.router)
api_router.include_router(followup.router)
api_router.include_router(ai.router)
api_router.include_router(reports.router)
api_router.include_router(webhooks.router)
api_router.include_router(public.router)
api_router.include_router(whatsapp.router)
api_router.include_router(reminders.router)
