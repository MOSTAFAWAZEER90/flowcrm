from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class PublicLeadIn(BaseModel):
    """Public web-to-lead form payload (no auth)."""

    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    message: str | None = Field(default=None, max_length=4000)


class PublicLeadResult(BaseModel):
    ok: bool
    created: bool
    is_hot_lead: bool
    contact_id: str
