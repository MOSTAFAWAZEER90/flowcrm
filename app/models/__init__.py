"""SQLAlchemy models. Importing this package registers every table on Base."""
from __future__ import annotations

from app.models.automation_log import AutomationLog
from app.models.base import Base
from app.models.channel_connection import ChannelConnection
from app.models.contact import Contact
from app.models.contact_note import ContactNote
from app.models.conversation import Conversation
from app.models.deal import Deal
from app.models.deal_stage_history import DealStageHistory
from app.models.followup_sequence import FollowupSequence
from app.models.message import Message
from app.models.organization import Organization
from app.models.task import Task
from app.models.user import User
from app.models.webhook_event import WebhookEvent

__all__ = [
    "AutomationLog",
    "Base",
    "ChannelConnection",
    "Contact",
    "ContactNote",
    "Conversation",
    "Deal",
    "DealStageHistory",
    "FollowupSequence",
    "Message",
    "Organization",
    "Task",
    "User",
    "WebhookEvent",
]
