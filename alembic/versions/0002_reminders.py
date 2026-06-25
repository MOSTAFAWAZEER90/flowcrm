"""reminders table — customer-chosen follow-up time (feature #2)

Revision ID: 0002_reminders
Revises: 0001_initial
Create Date: 2026-06-24

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_reminders"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_ORG = (
    "current_setting('app.bypass_rls', true) = 'on' "
    "OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE reminders (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            contact_id uuid NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            remind_at timestamptz NOT NULL,
            message text,
            channel varchar(40) NOT NULL DEFAULT 'whatsapp',
            status varchar(20) NOT NULL DEFAULT 'pending',
            sent_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_reminders_org_id ON reminders(org_id)")
    op.execute("CREATE INDEX ix_reminders_contact_id ON reminders(contact_id)")
    op.execute("CREATE INDEX ix_reminders_due ON reminders(status, remind_at)")
    op.execute(
        "CREATE TRIGGER trg_reminders_updated_at BEFORE UPDATE ON reminders "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )
    op.execute("ALTER TABLE reminders ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reminders FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON reminders "
        f"USING ({_RLS_ORG}) WITH CHECK ({_RLS_ORG})"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reminders CASCADE")
