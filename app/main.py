"""FlowCRM FastAPI application factory."""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.core.config import settings
from app.core.db import dispose_engine
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.routers import api_router
from app.workers.queue import get_pool

log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("startup", app=settings.app_name, version=__version__, env=settings.environment)
    try:
        app.state.arq = await get_pool()
    except Exception as exc:  # Redis optional at boot; webhooks degrade gracefully
        log.warning("arq_pool_unavailable", error=str(exc))
        app.state.arq = None
    yield
    if getattr(app.state, "arq", None) is not None:
        await app.state.arq.close()
    await dispose_engine()
    log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="AI-powered, multi-tenant omnichannel CRM backend.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log.info(
                "request",
                method=request.method,
                status=response.status_code,
                duration_ms=duration_ms,
            )
            response.headers["x-request-id"] = request_id
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log.exception("request_failed", method=request.method, duration_ms=duration_ms)
            raise
        finally:
            structlog.contextvars.unbind_contextvars("request_id", "path")

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "service": settings.app_name, "version": __version__}

    @app.get("/", tags=["health"])
    async def root() -> dict:
        return {"service": settings.app_name, "docs": "/docs", "ui": "/app/", "health": "/health"}

    # Serve the bundled web UI (dashboard + lead form) from the same origin,
    # so one deployment serves both API and frontend (no CORS, no hardcoded URL).
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.is_dir():
        app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="ui")

    return app


app = create_app()
