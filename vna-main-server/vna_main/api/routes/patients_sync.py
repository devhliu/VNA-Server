"""Patient sync API routes - Orthanc → VNA patient mapping sync."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.patient_sync_service import PatientSyncService

router = APIRouter(prefix="/patients", tags=["patients-sync"])


@router.post("/sync-from-dicom")
async def sync_patients_from_dicom(
    hospital_id: str = Query("default", description="Hospital/tenant ID"),
    dry_run: bool = Query(False, description="If True, don't persist changes"),
    db: AsyncSession = Depends(get_session),
) -> dict:
    svc = PatientSyncService(db)
    result = await svc.sync_from_dicom(hospital_id=hospital_id, dry_run=dry_run)
    return result


@router.get("/sync-status")
async def get_sync_status(db: AsyncSession = Depends(get_session)) -> dict:
    svc = PatientSyncService(db)
    return await svc.get_sync_status()
