"""Sync API - database sync, consistency verification, and repair."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.sync_service import SyncService
from vna_main.services.audit_service import AuditService

router = APIRouter(prefix="/sync", tags=["Sync"])


class RegisterServerRequest(BaseModel):
    source_db: str  # "dicom" or "bids"
    url: str


class SyncEventRequest(BaseModel):
    source_db: str
    event_type: str
    resource_id: str = ""
    payload: dict = {}


class VerifyRequest(BaseModel):
    dicom_url: Optional[str] = None
    bids_url: Optional[str] = None
    repair: bool = False


class RebuildRequest(BaseModel):
    dicom_url: Optional[str] = None
    bids_url: Optional[str] = None
    clear_existing: bool = False


@router.post("/register")
async def register_server(req: RegisterServerRequest, db: AsyncSession = Depends(get_session)):
    """Register a DICOM or BIDS sub-server for sync."""
    svc = SyncService(db)
    result = await svc.register_server(req.source_db, req.url)
    await db.commit()
    return result


@router.get("/status")
async def sync_status(db: AsyncSession = Depends(get_session)):
    """Get sync status for all registered servers."""
    svc = SyncService(db)
    status = await svc.get_status()
    servers = status.get("servers", {})
    return {
        "dicom": servers.get("dicom", {"total_events": 0, "pending_events": 0}),
        "bids": servers.get("bids", {"total_events": 0, "pending_events": 0}),
        "servers": servers,
        "total_pending": status.get("total_pending", 0),
    }


@router.post("/trigger")
async def trigger_sync(
    source_db: Optional[str] = Query(None, description="dicom, bids, or all"),
    db: AsyncSession = Depends(get_session),
):
    """Trigger manual sync from sub-servers."""
    svc = SyncService(db)
    result = await svc.trigger_sync(source_db=source_db)
    await db.commit()
    return {"triggered": True, "pending_events": result["total_pending"], "processed_events": result["processed_events"], "source_db": source_db or "all"}


@router.post("/event")
async def receive_event(req: SyncEventRequest, db: AsyncSession = Depends(get_session)):
    """
    Receive sync event from sub-server.
    
    Event types:
      - resource.created, resource.updated, resource.deleted
      - label.updated
    """
    svc = SyncService(db)
    audit_svc = AuditService(db)
    event = await svc.receive_event(req.model_dump())
    await db.commit()
    
    # Audit log for received events (but not processed ones to avoid noise)
    if not event.processed:
        await audit_svc.log(
            action="receive_event",
            resource_type="sync_event",
            resource_id=str(event.id),
            details={
                "source_db": event.source_db,
                "event_type": event.event_type,
                "resource_id": event.resource_id
            }
        )
    
    return {
        "id": event.id,
        "source_db": event.source_db,
        "event_type": event.event_type,
        "resource_id": event.resource_id,
        "processed": event.processed,
        "received": True,
    }


@router.get("/events")
async def list_events(
    source_db: Optional[str] = None,
    event_type: Optional[str] = None,
    processed: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
):
    """List sync events."""
    svc = SyncService(db)
    events, total = await svc.list_events(
        source_db=source_db,
        event_type=event_type,
        processed=processed,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "items": [
            {
                "id": e.id,
                "source_db": e.source_db,
                "event_type": e.event_type,
                "resource_id": e.resource_id,
                "processed": e.processed,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.post("/verify")
async def verify_consistency(req: VerifyRequest, db: AsyncSession = Depends(get_session)):
    """
    Verify consistency across Main DB and sub-servers.
    
    Checks:
    - Resources in Main DB exist in sub-servers
    - Resources in sub-servers have Main DB entries
    - Labels match across systems
    
    Set repair=true to auto-fix inconsistencies.
    """
    svc = SyncService(db)
    audit_svc = AuditService(db)
    result = await svc.verify_consistency(
        dicom_url=req.dicom_url,
        bids_url=req.bids_url,
        repair=req.repair,
    )
    await db.commit()
    
    # Audit log
    await audit_svc.log(
        action="verify_consistency",
        resource_type="sync_verification",
        resource_id="verify_request",
        details={
            "dicom_url": req.dicom_url,
            "bids_url": req.bids_url,
            "repair": req.repair,
            "status": result.get("status"),
            "summary": result.get("summary")
        }
    )
    
    return result


@router.post("/rebuild")
async def rebuild_index(req: RebuildRequest, db: AsyncSession = Depends(get_session)):
    """
    Rebuild main DB index from sub-servers.
    
    WARNING: If clear_existing=true, all index data will be deleted first.
    Sub-servers are treated as the source of truth.
    """
    svc = SyncService(db)
    result = await svc.rebuild_index(
        dicom_url=req.dicom_url,
        bids_url=req.bids_url,
        clear_existing=req.clear_existing,
    )
    await db.commit()
    return result
