"""Health check API route."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.routing_service import RoutingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check(session: AsyncSession = Depends(get_session)):
    """Health status of all VNA components with live/ready/degraded reporting."""
    routing = RoutingService()
    sub_health = await routing.unified_health()

    # Check database connectivity using shared session
    db_status = "healthy"
    try:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.error("Database health check failed", exc_info=True)
        db_status = "unhealthy"

    # Check Redis if enabled
    redis_status = "disabled"
    try:
        from vna_main.config import settings
        if settings.REDIS_ENABLED:
             try:
                 import redis.asyncio as aioredis
                 r = aioredis.from_url(settings.REDIS_URL)
                 await r.ping()
                 redis_status = "healthy"
                 await r.close()
             except Exception:
                 logger.error("Redis health check failed", exc_info=True)
                 redis_status = "unhealthy"
    except Exception:
        logger.error("Redis config check failed", exc_info=True)
        redis_status = "disabled"

    # Determine overall status
    components_healthy = all([
        sub_health["dicom"]["status"] == "healthy",
        sub_health["bids"]["status"] == "healthy",
        db_status == "healthy",
    ])

    degraded = not components_healthy or redis_status == "unhealthy"

    return {
        "live": True,
        "ready": components_healthy,
        "degraded": degraded,
        "service": "vna-main-server",
        "status": "healthy" if components_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "main_server": {"status": "healthy"},
            "database": {"status": db_status},
            "redis": {"status": redis_status},
            "dicom_server": sub_health["dicom"],
            "bids_server": sub_health["bids"],
        },
    }
