"""Application configuration loaded from environment / .env (Pydantic v2)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "FlowCRM"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    api_v1_prefix: str = "/v1"

    # --- Database ---
    database_url: str = Field(alias="DATABASE_URL")
    db_echo: bool = Field(default=False, alias="DB_ECHO")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    db_statement_cache_size: int = Field(default=0, alias="DB_STATEMENT_CACHE_SIZE")
    # Enable TLS for the DB connection (required by cloud Postgres: Supabase/Neon).
    db_ssl: bool = Field(default=False, alias="DB_SSL")
    # Restricted role the request session switches into so RLS is enforced.
    db_app_role: str = Field(default="flowcrm_app", alias="DB_APP_ROLE")

    # --- Redis / ARQ ---
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # --- OpenAI ---
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_timeout: float = Field(default=30.0, alias="OPENAI_TIMEOUT")

    # --- AI persona (replies sound like a real human sales rep, never a bot) ---
    ai_agent_name: str = Field(default="Omar", alias="AI_AGENT_NAME")
    ai_company_name: str = Field(default="our team", alias="AI_COMPANY_NAME")

    # --- JWT ---
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_alg: str = Field(default="HS256", alias="JWT_ALG")
    jwt_access_ttl_minutes: int = Field(default=60 * 12, alias="JWT_ACCESS_TTL_MINUTES")
    jwt_invite_ttl_hours: int = Field(default=72, alias="JWT_INVITE_TTL_HOURS")

    # --- Webhook signing secrets ---
    meta_app_secret: str | None = Field(default=None, alias="META_APP_SECRET")
    whatsapp_app_secret: str | None = Field(default=None, alias="WHATSAPP_APP_SECRET")
    calendly_signing_key: str | None = Field(default=None, alias="CALENDLY_SIGNING_KEY")
    forms_webhook_secret: str | None = Field(default=None, alias="FORMS_WEBHOOK_SECRET")

    # WhatsApp Cloud API (Meta) webhook + outbound sending
    whatsapp_verify_token: str | None = Field(default=None, alias="WHATSAPP_VERIFY_TOKEN")
    whatsapp_org_slug: str = Field(default="acme-inc", alias="WHATSAPP_ORG_SLUG")
    whatsapp_access_token: str | None = Field(default=None, alias="WHATSAPP_ACCESS_TOKEN")
    whatsapp_phone_number_id: str | None = Field(default=None, alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_api_version: str = Field(default="v21.0", alias="WHATSAPP_API_VERSION")

    # Where to send owner notifications/summaries (Telegram bot — easiest, no card)
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    owner_telegram_chat_id: str | None = Field(default=None, alias="OWNER_TELEGRAM_CHAT_ID")

    # Facebook Page comments -> AI reply + private message (feature #6, ManyChat-style)
    facebook_verify_token: str | None = Field(default=None, alias="FACEBOOK_VERIFY_TOKEN")
    facebook_page_access_token: str | None = Field(default=None, alias="FACEBOOK_PAGE_ACCESS_TOKEN")
    facebook_org_slug: str = Field(default="acme-inc", alias="FACEBOOK_ORG_SLUG")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    def webhook_secret(self, source: str) -> str | None:
        """Return the configured signing secret for a webhook source."""
        return {
            "meta": self.meta_app_secret,
            "whatsapp": self.whatsapp_app_secret,
            "calendly": self.calendly_signing_key,
            "forms": self.forms_webhook_secret,
        }.get(source)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
