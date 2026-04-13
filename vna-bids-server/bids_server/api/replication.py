"""Replication API routes for multi-datacenter support."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.services.replication_service import ReplicationService

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/replication", tags=["replication"])


class ReplicationPayload(BaseModel):
    source_datacenter: str
    resource_type: str
    resource_id: str
    action: str
    data: dict[str, Any]
    timestamp: str


@router.get("/status")
async def get_replication_status(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ReplicationService(db)
    try:
        return await svc.get_sync_status()
    finally:
        await svc.close()


@router.post("/receive")
async def receive_replication(
    payload: ReplicationPayload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ReplicationService(db)
    try:
        return await svc.receive_changes(
            source_datacenter=payload.source_datacenter,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            action=payload.action,
            data=payload.data,
        )
    finally:
        await svc.close()


@router.post("/sync")
async def trigger_sync(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from bids_server.services.replication_service import run_replication_sync
    
    try:
        await run_replication_sync(db)
        return {"status": "sync_completed", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error("Replication sync failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending")
async def get_pending_items(
    since: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    svc = ReplicationService(db)
    try:
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                logger.debug("Invalid 'since' parameter: %s", since)
        
        return await svc.get_pending_sync_items(since=since_dt, limit=limit)
    finally:
        await svc.close()
