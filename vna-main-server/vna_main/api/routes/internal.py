"""Internal API routes — cross-service endpoints not exposed publicly."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import SyncEvent, get_session
from vna_main.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


class DicomSyncEvent(BaseModel):
    event_type: str = Field(..., description="e.g. dicom_received, study_stable")
    resource_type: str = Field(default="study")
    orthanc_id: str = ""
    study_uid: str = ""
    patient_id: str = ""
    patient_name: str = ""
    study_description: str = ""
    modalities: list[str] = Field(default_factory=list)
    series_count: int = 0
    instance_count: int = 0
    timestamp: str = ""


@router.post("/sync/dicom")
async def sync_dicom_event(
    req: DicomSyncEvent,
    db: AsyncSession = Depends(get_session),
):
    """Receive DICOM sync event from Orthanc Lua callback."""
    event = SyncEvent(
        source_db="dicom",
        event_type=req.event_type,
        resource_id=req.orthanc_id,
        payload=req.model_dump(),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    
    # Audit log
    audit_svc = AuditService(db)
    await audit_svc.log(
        action="sync",
        resource_type="dicom_event",
        resource_id=str(event.id),
        details={
            "event_type": req.event_type,
            "study_uid": req.study_uid,
            "patient_id": req.patient_id,
            "orthanc_id": req.orthanc_id
        }
    )
    
    logger.info("DICOM sync event received: id=%s type=%s study=%s", event.id, req.event_type, req.study_uid)
    return {"received": True, "event_id": event.id}


@router.get("/status")
async def internal_status():
    """Internal status endpoint for cross-service health checks."""
    return {
        "service": "vna-main-server",
        "live": True,
        "ready": True,
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
