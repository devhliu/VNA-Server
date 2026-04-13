"""BIDS Server - Main application entry point."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from bids_server.api.deps.auth import require_bids_api_key
from bids_server.config import settings
from bids_server.db.session import async_session, engine
from bids_server.models.database import Base
from bids_server.services.task_service import task_service
from bids_server.core.webhook_manager import webhook_manager
from vna_common.middleware.request_id import RequestIDMiddleware
from vna_common.middleware.api_version import APIVersionMiddleware
from bids_server.api.middleware.rate_limit import RateLimitMiddleware
from vna_common.middleware.logging import setup_json_logging
from vna_common.responses import ErrorResponse

logger = logging.getLogger(__name__)


async def check_database() -> bool:
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("Database health check failed", exc_info=True)
        return False


def check_storage() -> bool:
    try:
        root = Path(settings.bids_root)
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".healthcheck"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        logger.warning("Storage health check failed", exc_info=True)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    if settings.log_format == "json":
        setup_json_logging(settings.log_level)

    logger.info("Expecting PostgreSQL schema to be managed by Alembic before app startup")

    from bids_server.api.modalities import load_default_modalities

    async with async_session() as db:
        await load_default_modalities(db)

    await task_service.run_startup_reclaim()
    worker_task = None
    delivery_task = None
    if settings.enable_background_worker:
        worker_task = asyncio.create_task(task_service.run_forever())
        app.state.worker_task = worker_task
        delivery_task = asyncio.create_task(webhook_manager.run_delivery_loop())
        app.state.delivery_task = delivery_task

    yield

    if delivery_task is not None:
        delivery_task.cancel()
        try:
            await delivery_task
        except asyncio.CancelledError:
            pass
    if worker_task is not None:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    await engine.dispose()


app = FastAPI(
    title="BIDS Server",
    description="BIDSweb API - VNA BIDS Data Management Service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIVersionMiddleware, version="v1")
app.add_middleware(RequestIDMiddleware)

protected_dependencies = [Depends(require_bids_api_key)]

from bids_server.api import (  # noqa: E402
    store,
    objects,
    query,
    subjects,
    sessions,
    labels,
    annotations,
    tasks,
    webhooks,
    modalities,
    verify,
    rebuild,
    replication,
    validation,
)

app.include_router(store.router, dependencies=protected_dependencies)
app.include_router(objects.router, dependencies=protected_dependencies)
app.include_router(query.router, dependencies=protected_dependencies)
app.include_router(subjects.router, dependencies=protected_dependencies)
app.include_router(sessions.router, dependencies=protected_dependencies)
app.include_router(labels.router, dependencies=protected_dependencies)
app.include_router(annotations.router, dependencies=protected_dependencies)
app.include_router(tasks.router, dependencies=protected_dependencies)
app.include_router(webhooks.router, dependencies=protected_dependencies)
app.include_router(modalities.router, dependencies=protected_dependencies)
app.include_router(verify.router, dependencies=protected_dependencies)
app.include_router(rebuild.router, dependencies=protected_dependencies)
app.include_router(replication.router, dependencies=protected_dependencies)
app.include_router(validation.router, dependencies=protected_dependencies)


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "service": "BIDS Server",
        "version": "1.0.0",
        "protocol": "BIDSweb",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Operational health endpoint for the BIDS service."""
    database_ok = await check_database()
    storage_ok = check_storage()
    retrying_tasks = 0
    failed_webhooks = 0
    retrying_webhooks = 0

    if database_ok:
        async with async_session() as db:
            retrying_tasks = await task_service.count_retrying_tasks(db)
            delivery_counts = await webhook_manager.count_statuses(db)
            failed_webhooks = delivery_counts["failed"]
            retrying_webhooks = delivery_counts["retrying"]

    ready = database_ok and storage_ok
    degraded = failed_webhooks >= 1 or retrying_webhooks > 10 or retrying_tasks > 5
    return {
        "live": True,
        "ready": ready,
        "degraded": degraded,
        "checks": {
            "database": "healthy" if database_ok else "unhealthy",
            "storage": "healthy" if storage_ok else "unhealthy",
            "webhooks": "degraded" if (failed_webhooks >= 1 or retrying_webhooks > 10) else "healthy",
        },
        "stats": {
            "retrying_tasks": retrying_tasks,
            "failed_webhooks": failed_webhooks,
            "retrying_webhooks": retrying_webhooks,
        },
    }


@app.post("/api/v1/internal/status", tags=["Health"])
async def internal_status():
    """Internal status endpoint for cross-service health checks."""
    return {
        "service": "bids-server",
        "live": True,
        "ready": await check_database(),
        "version": "1.0.0",
        "worker_enabled": settings.enable_background_worker,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled exception occurred during request (request_id=%s)", request_id)
    body = ErrorResponse(
        error="Internal server error",
        details={"message": f"An internal error occurred. Contact support with request ID: {request_id}"},
        path=str(request.url.path),
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))
