# FlowCRM

An **AI-powered, multi-tenant omnichannel CRM** backend built with FastAPI,
async SQLAlchemy 2.0, PostgreSQL (with Row Level Security), Redis + ARQ, and the
OpenAI SDK.

It is designed to sit behind an automation layer (e.g. **n8n**) that ingests
leads from messaging channels and forms, and exposes clean, JWT-protected,
org-scoped APIs for contacts, conversations, deals, tasks, follow-up cadences,
AI utilities, reports and inbound webhooks.

---

## Highlights

- **True multi-tenancy** enforced at the database layer with PostgreSQL **Row
  Level Security**. Each request switches into a restricted DB role and pins
  `app.current_org` via `SET LOCAL` / `set_config(..., is_local => true)`.
- **Layered architecture**: `routers → services → repositories → models`. No
  business logic in routers.
- **Async everywhere** — async SQLAlchemy sessions and async OpenAI calls.
- **RBAC** roles (`admin`, `manager`, `sales_rep`, `support`) as composable
  FastAPI dependencies.
- **Deterministic, unit-tested core logic**: lead-score blending and follow-up
  cadence are pure functions.
- **Graceful AI degradation**: if `OPENAI_API_KEY` is unset, AI features fall
  back to a local heuristic so the app stays fully functional.

---

## Architecture

### Layers

```
routers/        HTTP surface, validation, (de)serialization — no business logic
services/       Business logic, orchestration, transactions
repositories/   Query building / persistence
models/         SQLAlchemy ORM models
core/           config, security/JWT, db session, deps, logging, errors
workers/        ARQ background tasks
```

### Multi-tenancy & Row Level Security

Isolation is enforced by Postgres, not just application code:

1. Migrations and the **auth/bootstrap** path connect as the **owner** role
   (`DATABASE_URL`). The owner **bypasses** RLS, which is exactly what login
   needs (it must look a user up across tenants) and what registration needs
   (it creates the org + first admin before any tenant context exists).
2. Every **normal request** goes through `get_db`, which:
   - `SET LOCAL ROLE "flowcrm_app"` — a restricted role that **is** subject to
     RLS (it does not own the tables),
   - `set_config('app.current_org', <org from JWT>, true)`,
   - `set_config('app.current_user_id', <user from JWT>, true)`.
3. Each tenant table has a policy:
   ```sql
   USING      (org_id = NULLIF(current_setting('app.current_org', true), '')::uuid)
   WITH CHECK (org_id = NULLIF(current_setting('app.current_org', true), '')::uuid)
   ```
   With no org set, `NULLIF(...)` is `NULL` → no rows match → fail-closed.

Everything in a request runs in **one transaction** (a unit-of-work): services
only `flush`; the `get_db` dependency `commit`s once at the end. This keeps
`SET LOCAL` valid for the whole request and avoids leaking tenant context across
pooled connections.

> The connecting role needs `CREATEROLE` so the migration can create
> `flowcrm_app`. The local docker Postgres superuser and Supabase's `postgres`
> role both satisfy this.

### Triggers

- `set_updated_at()` — stamps `updated_at` on every update.
- `deal_stamp_stage()` / `deal_log_stage()` — on deal insert/stage-change, set
  `stage_changed_at`/`closed_at` and append a `deal_stage_history` row
  (attributed to `app.current_user_id`).

---

## Tech stack

Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2.0 (async) + Alembic, PostgreSQL
(asyncpg), Pydantic v2, Redis + ARQ, OpenAI SDK, python-jose + passlib[bcrypt],
structlog, pytest.

---

## Quickstart (Docker)

```bash
cd flowcrm
cp .env.example .env            # optional; compose has sensible dev defaults
export JWT_SECRET="$(openssl rand -hex 32)"   # optional
export OPENAI_API_KEY="sk-..."                # optional (heuristic fallback otherwise)

docker compose up --build
```

This starts **postgres**, **redis**, the **api** (which runs `alembic upgrade
head` then serves on `:8000`), and the ARQ **worker**.

- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/health

---

## Local development

```bash
cd flowcrm
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then edit DATABASE_URL, JWT_SECRET, etc.

# Start Postgres + Redis (or just the data services from compose):
docker compose up -d postgres redis

# 1) Run migrations
alembic upgrade head

# 2) Start the API
uvicorn app.main:app --reload

# 3) Start the ARQ worker (separate terminal)
arq app.workers.arq_worker.WorkerSettings
```

### Environment variables (`.env`)

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | async DSN, e.g. `postgresql+asyncpg://flowcrm:flowcrm@localhost:5432/flowcrm` |
| `REDIS_URL` | ARQ broker, e.g. `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | optional; omit to use the local heuristic |
| `OPENAI_MODEL` | defaults to `gpt-4o-mini` |
| `JWT_SECRET` / `JWT_ALG` | JWT signing secret / algorithm (`HS256`) |
| `DB_APP_ROLE` | restricted RLS role name (default `flowcrm_app`) |
| `DB_STATEMENT_CACHE_SIZE` | set `0` behind PgBouncer / Supabase pooler (`:6543`) |
| `META_APP_SECRET`, `WHATSAPP_APP_SECRET`, `CALENDLY_SIGNING_KEY`, `FORMS_WEBHOOK_SECRET` | webhook HMAC secrets |

### Supabase

Use the asyncpg driver and the transaction pooler, and disable the statement
cache:

```
DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:6543/postgres
DB_STATEMENT_CACHE_SIZE=0
```

---

## API overview (prefix `/v1`)

**Auth**
- `POST /v1/auth/register` — create org + admin, returns JWT
- `POST /v1/auth/login` — returns JWT (`org_id` + `role` claims)
- `POST /v1/auth/invite` — admin/manager creates an invite token
- `POST /v1/auth/invite/accept` — invitee sets a password, returns JWT

**Contacts**
- `GET /v1/contacts` — list / search (name, email, tag) / filter / paginate
- `POST /v1/contacts`, `PATCH /v1/contacts/{id}`
- `POST /v1/contacts/upsert` — **idempotent by `external_id`** (called by n8n);
  on first insert it also creates a conversation + first message and runs AI
  scoring

**Conversations & messages**
- `GET /v1/conversations?open=true`
- `GET /v1/conversations/{id}/messages`
- `POST /v1/conversations/{id}/messages` — outbound

**Deals**
- `GET/POST/PATCH /v1/deals` — stage changes auto-log to `deal_stage_history`
- `GET /v1/deals/{id}/history`

**Tasks**
- `GET/POST/PATCH /v1/tasks` — `POST` accepts `{title, due_in_minutes, created_by_ai}`

**Follow-up cadence** (called by n8n)
- `POST /v1/followup/enroll` `{external_id, template}`
- `GET  /v1/followup/due` — due sequences + contact info + `contact_replied`
- `POST /v1/followup/advance` `{sequence_id, sent_step}` — schedules next step
  (Day 1/3/7/14), deactivates after step 4
- `POST /v1/followup/complete` `{sequence_id, reason}`

**AI**
- `POST /v1/ai/classify` `{text}` → `{intent, buying_signal, lead_score, summary,
  suggested_reply, next_action, is_hot_lead}` (gpt-4o-mini, JSON mode)
- `POST /v1/ai/summarize` `{conversation_id}`
- `POST /v1/ai/reply` `{conversation_id, tone}`

**Reports**
- `GET /v1/reports/funnel | /pipeline | /sources | /team`

**Webhooks** (public, signature-verified, return 200 fast, enqueue to ARQ)
- `POST /v1/webhooks/{meta|whatsapp|calendly|forms}`

### Example: register then call an endpoint

```bash
TOKEN=$(curl -s localhost:8000/v1/auth/register \
  -H 'content-type: application/json' \
  -d '{"org_name":"Acme","full_name":"Ana","email":"ana@acme.io","password":"password123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl localhost:8000/v1/contacts -H "authorization: Bearer $TOKEN"
```

---

## Lead scoring

`services/scoring.py::blend_lead_score` blends the AI base score with
deterministic features (channel quality, recency, profile completeness, buying
signal). It is a **pure function** (unit-tested in `tests/test_scoring.py`).
Hot lead = `score >= 70 OR buying_signal`.

## Cadence

`services/cadence.py` implements the Day **1/3/7/14** schedule as pure functions
(unit-tested in `tests/test_cadence.py`). `GET /v1/followup/due` reports
`contact_replied=true` when the contact has any inbound message after
enrollment, so the automation can stop the sequence.

---

## Tests

Pure-logic tests run anywhere. DB-backed tests need a reachable Postgres (they
auto-skip if migrations can't be applied).

```bash
docker compose up -d postgres        # for the DB-backed tests
pip install -r requirements.txt
pytest -v
# point at a different DB:  TEST_DATABASE_URL=postgresql+asyncpg://... pytest
```

Included tests:
- `test_scoring.py` — lead-score blend function
- `test_cadence.py` — cadence step scheduling
- `test_upsert.py` — idempotent upsert (+ conversation/message seeding)
- `test_rls.py` — RLS isolation (org A cannot read/write org B)

---

## Production notes

- Run `alembic upgrade head` as a **separate deploy step** (the compose `api`
  service runs it inline only for dev convenience).
- Put the API behind TLS; rotate `JWT_SECRET`; set per-source webhook secrets.
- Scale ARQ workers horizontally; tune `max_jobs` / `job_timeout`.
- Logs are structured JSON in production (`ENVIRONMENT=production`).
