"""initial schema: enums, tables, indexes, triggers, RLS

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-19

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from app.core.config import settings

# Non-bypass role the request path switches into via SET ROLE. On Supabase set
# DB_APP_ROLE=authenticated (a built-in, non-bypass role that already exists);
# locally it defaults to flowcrm_app, which this migration creates.
APP_ROLE = settings.db_app_role

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# RLS predicate: the trusted auth/bootstrap path sets app.bypass_rls='on'
# (transaction-local) to read across tenants; every other path is org-scoped.
_RLS_ORG = (
    "current_setting('app.bypass_rls', true) = 'on' "
    "OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid"
)
_RLS_ID = (
    "current_setting('app.bypass_rls', true) = 'on' "
    "OR id = NULLIF(current_setting('app.current_org', true), '')::uuid"
)

# Tables that carry an org_id and must be tenant-isolated by RLS.
TENANT_TABLES = [
    "users",
    "channel_connections",
    "contacts",
    "contact_notes",
    "conversations",
    "messages",
    "deals",
    "deal_stage_history",
    "tasks",
    "followup_sequences",
    "automation_logs",
]

# Tables with an updated_at column that should be auto-stamped by trigger.
UPDATED_AT_TABLES = [
    "organizations",
    "users",
    "channel_connections",
    "contacts",
    "contact_notes",
    "conversations",
    "messages",
    "deals",
    "tasks",
    "followup_sequences",
    "automation_logs",
    "webhook_events",
]

ENUM_DDL = [
    "CREATE TYPE user_role AS ENUM ('admin','manager','sales_rep','support')",
    "CREATE TYPE lead_channel AS ENUM ('messenger','instagram','whatsapp','web_form',"
    "'landing_page','fb_lead_form','google_form','calendly','email','manual')",
    "CREATE TYPE pipeline_stage AS ENUM ('new_lead','contacted','interested','qualified',"
    "'meeting_scheduled','proposal_sent','negotiation','won','lost')",
    "CREATE TYPE contact_status AS ENUM ('active','unqualified','nurturing','customer','churned')",
    "CREATE TYPE message_direction AS ENUM ('inbound','outbound')",
    "CREATE TYPE task_status AS ENUM ('open','done','cancelled')",
    "CREATE TYPE ai_intent AS ENUM ('inquiry','pricing','booking','support','complaint','spam',"
    "'ready_to_buy','not_interested','other')",
]

TABLE_DDL = [
    """
    CREATE TABLE organizations (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        name varchar(255) NOT NULL,
        slug varchar(120) NOT NULL UNIQUE,
        plan varchar(50) NOT NULL DEFAULT 'free',
        status varchar(50) NOT NULL DEFAULT 'active',
        white_label jsonb NOT NULL DEFAULT '{}',
        settings jsonb NOT NULL DEFAULT '{}',
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE users (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        email varchar(320) NOT NULL,
        full_name varchar(255) NOT NULL,
        role user_role NOT NULL DEFAULT 'sales_rep',
        auth_uid varchar(255) NOT NULL,
        is_active boolean NOT NULL DEFAULT true,
        last_seen_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_users_org_email UNIQUE (org_id, email)
    )
    """,
    """
    CREATE TABLE channel_connections (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        channel lead_channel NOT NULL,
        external_id varchar(255) NOT NULL,
        display_name varchar(255),
        credentials jsonb NOT NULL DEFAULT '{}',
        is_active boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_channel_conn UNIQUE (org_id, channel, external_id)
    )
    """,
    """
    CREATE TABLE contacts (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        full_name varchar(255) NOT NULL,
        email varchar(320),
        phone varchar(50),
        source lead_channel NOT NULL DEFAULT 'manual',
        status contact_status NOT NULL DEFAULT 'active',
        lead_score integer NOT NULL DEFAULT 0,
        tags text[] NOT NULL DEFAULT '{}',
        assigned_to uuid REFERENCES users(id) ON DELETE SET NULL,
        external_refs jsonb NOT NULL DEFAULT '{}',
        custom_fields jsonb NOT NULL DEFAULT '{}',
        last_activity_at timestamptz,
        deleted_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE contact_notes (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        contact_id uuid NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
        author_id uuid REFERENCES users(id) ON DELETE SET NULL,
        body text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE conversations (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        contact_id uuid NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
        channel lead_channel NOT NULL,
        connection_id uuid REFERENCES channel_connections(id) ON DELETE SET NULL,
        external_thread varchar(255),
        is_open boolean NOT NULL DEFAULT true,
        last_message_at timestamptz,
        unread_count integer NOT NULL DEFAULT 0,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_conversation_thread UNIQUE (org_id, channel, external_thread)
    )
    """,
    """
    CREATE TABLE messages (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        direction message_direction NOT NULL,
        sender_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
        body text,
        attachments jsonb NOT NULL DEFAULT '[]',
        external_id varchar(255),
        ai_intent ai_intent,
        ai_sentiment numeric(4,3),
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_message_external UNIQUE (org_id, external_id)
    )
    """,
    """
    CREATE TABLE deals (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        contact_id uuid NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
        title varchar(255) NOT NULL,
        stage pipeline_stage NOT NULL DEFAULT 'new_lead',
        value numeric(14,2) NOT NULL DEFAULT 0,
        currency varchar(3) NOT NULL DEFAULT 'USD',
        owner_id uuid REFERENCES users(id) ON DELETE SET NULL,
        probability integer NOT NULL DEFAULT 0,
        expected_close date,
        lost_reason text,
        stage_changed_at timestamptz,
        closed_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE deal_stage_history (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        deal_id uuid NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
        from_stage pipeline_stage,
        to_stage pipeline_stage NOT NULL,
        changed_by uuid REFERENCES users(id) ON DELETE SET NULL,
        changed_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE tasks (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        contact_id uuid REFERENCES contacts(id) ON DELETE CASCADE,
        deal_id uuid REFERENCES deals(id) ON DELETE CASCADE,
        assigned_to uuid REFERENCES users(id) ON DELETE SET NULL,
        title varchar(255) NOT NULL,
        description text,
        due_at timestamptz,
        status task_status NOT NULL DEFAULT 'open',
        created_by_ai boolean NOT NULL DEFAULT false,
        completed_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE followup_sequences (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        contact_id uuid NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
        template varchar(120) NOT NULL DEFAULT 'default',
        current_step integer NOT NULL DEFAULT 0,
        next_run_at timestamptz,
        is_active boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE automation_logs (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        workflow varchar(120) NOT NULL,
        entity_type varchar(60) NOT NULL,
        entity_id uuid,
        status varchar(40) NOT NULL DEFAULT 'ok',
        payload jsonb NOT NULL DEFAULT '{}',
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE webhook_events (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
        source varchar(40) NOT NULL,
        external_id varchar(255) NOT NULL,
        raw jsonb NOT NULL DEFAULT '{}',
        processed boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT uq_webhook_source_external UNIQUE (source, external_id)
    )
    """,
]

INDEX_DDL = [
    "CREATE INDEX ix_users_org_id ON users(org_id)",
    "CREATE INDEX ix_users_email ON users(email)",
    "CREATE INDEX ix_channel_connections_org_id ON channel_connections(org_id)",
    "CREATE INDEX ix_contacts_org_id ON contacts(org_id)",
    "CREATE INDEX ix_contacts_email ON contacts(email)",
    "CREATE INDEX ix_contacts_phone ON contacts(phone)",
    "CREATE INDEX ix_contacts_assigned_to ON contacts(assigned_to)",
    "CREATE INDEX ix_contacts_status ON contacts(status)",
    # GIN index for tag membership queries (tags && ARRAY[...]).
    "CREATE INDEX ix_contacts_tags_gin ON contacts USING gin (tags)",
    # Trigram index for fuzzy / ILIKE search on full_name.
    "CREATE INDEX ix_contacts_full_name_trgm ON contacts USING gin (full_name gin_trgm_ops)",
    "CREATE INDEX ix_contact_notes_org_id ON contact_notes(org_id)",
    "CREATE INDEX ix_contact_notes_contact_id ON contact_notes(contact_id)",
    "CREATE INDEX ix_conversations_org_id ON conversations(org_id)",
    "CREATE INDEX ix_conversations_contact_id ON conversations(contact_id)",
    "CREATE INDEX ix_conversations_is_open ON conversations(is_open)",
    "CREATE INDEX ix_messages_org_id ON messages(org_id)",
    "CREATE INDEX ix_messages_conversation_id ON messages(conversation_id)",
    "CREATE INDEX ix_deals_org_id ON deals(org_id)",
    "CREATE INDEX ix_deals_contact_id ON deals(contact_id)",
    "CREATE INDEX ix_deals_stage ON deals(stage)",
    "CREATE INDEX ix_deals_owner_id ON deals(owner_id)",
    "CREATE INDEX ix_deal_stage_history_org_id ON deal_stage_history(org_id)",
    "CREATE INDEX ix_deal_stage_history_deal_id ON deal_stage_history(deal_id)",
    "CREATE INDEX ix_tasks_org_id ON tasks(org_id)",
    "CREATE INDEX ix_tasks_contact_id ON tasks(contact_id)",
    "CREATE INDEX ix_tasks_deal_id ON tasks(deal_id)",
    "CREATE INDEX ix_tasks_assigned_to ON tasks(assigned_to)",
    "CREATE INDEX ix_tasks_due_at ON tasks(due_at)",
    "CREATE INDEX ix_tasks_status ON tasks(status)",
    "CREATE INDEX ix_followup_sequences_org_id ON followup_sequences(org_id)",
    "CREATE INDEX ix_followup_sequences_contact_id ON followup_sequences(contact_id)",
    "CREATE INDEX ix_followup_sequences_next_run_at ON followup_sequences(next_run_at)",
    "CREATE INDEX ix_followup_sequences_is_active ON followup_sequences(is_active)",
    "CREATE INDEX ix_automation_logs_org_id ON automation_logs(org_id)",
    "CREATE INDEX ix_automation_logs_workflow ON automation_logs(workflow)",
    "CREATE INDEX ix_webhook_events_org_id ON webhook_events(org_id)",
    "CREATE INDEX ix_webhook_events_processed ON webhook_events(processed)",
]

FN_SET_UPDATED_AT = """
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

FN_DEAL_STAMP_STAGE = """
CREATE OR REPLACE FUNCTION deal_stamp_stage() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.stage_changed_at IS NULL THEN
            NEW.stage_changed_at := now();
        END IF;
        IF NEW.stage IN ('won','lost') AND NEW.closed_at IS NULL THEN
            NEW.closed_at := now();
        END IF;
    ELSIF TG_OP = 'UPDATE' AND NEW.stage IS DISTINCT FROM OLD.stage THEN
        NEW.stage_changed_at := now();
        IF NEW.stage IN ('won','lost') THEN
            NEW.closed_at := now();
        ELSE
            NEW.closed_at := NULL;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

FN_DEAL_LOG_STAGE = """
CREATE OR REPLACE FUNCTION deal_log_stage() RETURNS trigger AS $$
DECLARE
    actor uuid := NULLIF(current_setting('app.current_user_id', true), '')::uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO deal_stage_history (org_id, deal_id, from_stage, to_stage, changed_by, changed_at)
        VALUES (NEW.org_id, NEW.id, NULL, NEW.stage, actor, now());
    ELSIF TG_OP = 'UPDATE' AND NEW.stage IS DISTINCT FROM OLD.stage THEN
        INSERT INTO deal_stage_history (org_id, deal_id, from_stage, to_stage, changed_by, changed_at)
        VALUES (NEW.org_id, NEW.id, OLD.stage, NEW.stage, actor, now());
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    bind = op.get_bind()

    # --- Extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # trigram search

    # --- Restricted role ---
    # Only create + grant if it doesn't already exist. On Supabase the role
    # (authenticated) is pre-provisioned with privileges, so we leave it alone.
    role_exists = (
        bind.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}).scalar()
        is not None
    )
    if not role_exists:
        op.execute(f'CREATE ROLE "{APP_ROLE}" NOLOGIN')

    # --- Enum types ---
    for ddl in ENUM_DDL:
        op.execute(ddl)

    # --- Tables ---
    for ddl in TABLE_DDL:
        op.execute(ddl)

    # --- Indexes ---
    for ddl in INDEX_DDL:
        op.execute(ddl)

    # --- Trigger functions ---
    op.execute(FN_SET_UPDATED_AT)
    op.execute(FN_DEAL_STAMP_STAGE)
    op.execute(FN_DEAL_LOG_STAGE)

    # updated_at triggers
    for table in UPDATED_AT_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    # deal stage triggers
    op.execute(
        "CREATE TRIGGER trg_deals_stamp_stage BEFORE INSERT OR UPDATE ON deals "
        "FOR EACH ROW EXECUTE FUNCTION deal_stamp_stage()"
    )
    op.execute(
        "CREATE TRIGGER trg_deals_log_stage AFTER INSERT OR UPDATE ON deals "
        "FOR EACH ROW EXECUTE FUNCTION deal_log_stage()"
    )

    # --- Row Level Security ---
    # FORCE so the table owner (the connecting role, incl. Supabase 'postgres')
    # is also subject to RLS. The trusted auth/bootstrap path opts out per
    # transaction via app.bypass_rls='on'; everything else is org-scoped.
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({_RLS_ORG}) WITH CHECK ({_RLS_ORG})"
        )

    # organizations isolate on id rather than org_id
    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON organizations "
        f"USING ({_RLS_ID}) WITH CHECK ({_RLS_ID})"
    )

    # --- Grants for a freshly-created (local) role ---
    if not role_exists:
        # Membership so the connecting role can SET ROLE into it.
        op.execute(f'GRANT "{APP_ROLE}" TO CURRENT_USER')
        op.execute(f'GRANT USAGE ON SCHEMA public TO "{APP_ROLE}"')
        op.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{APP_ROLE}"'
        )
        op.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{APP_ROLE}"')


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organizations")
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.execute("DROP TRIGGER IF EXISTS trg_deals_log_stage ON deals")
    op.execute("DROP TRIGGER IF EXISTS trg_deals_stamp_stage ON deals")
    for table in UPDATED_AT_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")

    op.execute("DROP FUNCTION IF EXISTS deal_log_stage()")
    op.execute("DROP FUNCTION IF EXISTS deal_stamp_stage()")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    for table in [
        "webhook_events",
        "automation_logs",
        "followup_sequences",
        "tasks",
        "deal_stage_history",
        "deals",
        "messages",
        "conversations",
        "contact_notes",
        "contacts",
        "channel_connections",
        "users",
        "organizations",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    for enum_name in [
        "ai_intent",
        "task_status",
        "message_direction",
        "contact_status",
        "pipeline_stage",
        "lead_channel",
        "user_role",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
