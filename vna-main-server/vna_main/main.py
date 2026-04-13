"""VNA Main Server - FastAPI application."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from vna_main.api.deps.auth import require_vna_api_key
from vna_main.api.routes import (
    audit,
    health,
    internal,
    labels,
    monitoring,
    patients,
    patients_sync,
    projects,
    query,
    resources,
    routing,
    sync,
    treatments,
    versions,
    webhooks,
)
from vna_main.config import settings
from vna_main.models.database import init_db
from vna_common.middleware.request_id import RequestIDMiddleware
from vna_common.middleware.logging import setup_json_logging
from vna_common.middleware.api_version import APIVersionMiddleware
from vna_main.api.middleware.rate_limit import RateLimitMiddleware
from vna_common.responses import ErrorResponse
from vna_main.services.cache_service import close_cache
from vna_main.services.http_client import close_http_client

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting VNA Main Server...")

    if settings.LOG_FORMAT == "json":
        setup_json_logging(settings.LOG_LEVEL)

    db_url = settings.DATABASE_URL
    if "sqlite" in db_url:
        try:
            await init_db()
            logger.info("SQLite database initialized")
        except Exception as e:
            logger.error("Failed to initialize database: %s", e)
            raise RuntimeError(f"Database initialization failed: {e}") from e
    else:
        logger.info("Expecting PostgreSQL schema to be managed by Alembic before app startup")

    yield
    logger.info("Shutting down VNA Main Server")
    try:
        await close_http_client()
        logger.info("HTTP client closed")
    except Exception as e:
        logger.error("Error closing HTTP client: %s", e)
    try:
        await close_cache()
        logger.info("Cache connection closed")
    except Exception as e:
        logger.error("Error closing cache connection: %s", e)


app = FastAPI(
    title="VNA Main Server",
    description="Central database and routing layer for VNA architecture",
    version="0.1.0",
    lifespan=lifespan,
)

protected_dependencies = [Depends(require_vna_api_key)]

app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIVersionMiddleware, version="v1")
app.add_middleware(RequestIDMiddleware)

app.include_router(internal.router, prefix="/api/v1")
app.include_router(resources.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(patients_sync.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(patients.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(labels.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(query.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(sync.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(health.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(versions.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(monitoring.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(routing.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(projects.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(treatments.router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(treatments.timeline_router, prefix="/api/v1", dependencies=protected_dependencies)
app.include_router(audit.router, prefix="/api/v1", dependencies=protected_dependencies)


@app.get("/")
async def root():
    return {"service": "vna-main-server", "version": "0.1.0"}


@app.get("/ui/routing")
async def routing_ui():
    ui_path = STATIC_DIR / "routing-ui.html"
    if ui_path.exists():
        return FileResponse(ui_path)
    return {"error": "UI not found"}


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


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
