"""ARQ worker entrypoint.

Run with:  arq app.workers.arq_worker.WorkerSettings
"""
from __future__ import annotations

from app.core.logging import configure_logging, get_logger
from app.workers.queue import redis_settings
from app.workers.tasks import process_webhook

log = get_logger("worker")


async def on_startup(ctx: dict) -> None:
    configure_logging()
    log.info("arq_worker_started")


async def on_shutdown(ctx: dict) -> None:
    log.info("arq_worker_stopped")


class WorkerSettings:
    functions = [process_webhook]
    redis_settings = redis_settings()
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = 20
    job_timeout = 60
    keep_result = 3600
