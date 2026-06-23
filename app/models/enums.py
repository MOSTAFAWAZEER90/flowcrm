"""Domain enumerations. PostgreSQL enum *types* are created in the migration;
SQLAlchemy columns reference them with ``create_type=False``."""
from __future__ import annotations

import enum

from sqlalchemy.dialects.postgresql import ENUM


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    sales_rep = "sales_rep"
    support = "support"


class LeadChannel(str, enum.Enum):
    messenger = "messenger"
    instagram = "instagram"
    whatsapp = "whatsapp"
    web_form = "web_form"
    landing_page = "landing_page"
    fb_lead_form = "fb_lead_form"
    google_form = "google_form"
    calendly = "calendly"
    email = "email"
    manual = "manual"


class PipelineStage(str, enum.Enum):
    new_lead = "new_lead"
    contacted = "contacted"
    interested = "interested"
    qualified = "qualified"
    meeting_scheduled = "meeting_scheduled"
    proposal_sent = "proposal_sent"
    negotiation = "negotiation"
    won = "won"
    lost = "lost"


class ContactStatus(str, enum.Enum):
    active = "active"
    unqualified = "unqualified"
    nurturing = "nurturing"
    customer = "customer"
    churned = "churned"


class MessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class TaskStatus(str, enum.Enum):
    open = "open"
    done = "done"
    cancelled = "cancelled"


class AIIntent(str, enum.Enum):
    inquiry = "inquiry"
    pricing = "pricing"
    booking = "booking"
    support = "support"
    complaint = "complaint"
    spam = "spam"
    ready_to_buy = "ready_to_buy"
    not_interested = "not_interested"
    other = "other"


def pg_enum(py_enum: type[enum.Enum], name: str) -> ENUM:
    """Reference an existing PostgreSQL enum type for a column."""
    return ENUM(
        py_enum,
        name=name,
        create_type=False,
        values_callable=lambda e: [member.value for member in e],
    )


# Canonical (python enum -> pg type name) registry, used by the migration.
ENUM_TYPES: dict[str, type[enum.Enum]] = {
    "user_role": UserRole,
    "lead_channel": LeadChannel,
    "pipeline_stage": PipelineStage,
    "contact_status": ContactStatus,
    "message_direction": MessageDirection,
    "task_status": TaskStatus,
    "ai_intent": AIIntent,
}
