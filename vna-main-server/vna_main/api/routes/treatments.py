"""Treatment event API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.treatment_service import TreatmentService
from vna_main.services.audit_service import AuditService

router = APIRouter(prefix="/treatments", tags=["treatments"])


class TreatmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_ref: str | None = None
    event_type: str
    event_date: str | None = None
    description: str | None = None
    outcome: str | None = None
    facility: str | None = None
    metadata: dict[str, Any] | None = None


class TreatmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_ref: str | None = None
    event_type: str | None = None
    event_date: str | None = None
    description: str | None = None
    outcome: str | None = None
    facility: str | None = None
    metadata: dict[str, Any] | None = None


def _parse_date(date_str: str | None) -> datetime | None:
    if date_str is None:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt
    except (ValueError, AttributeError):
        return None


@router.get("")
async def list_treatments(
    patient_ref: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    svc = TreatmentService(session)
    items, total = await svc.list_treatments(
        patient_ref=patient_ref, offset=offset, limit=limit,
    )
    return {"total": total, "items": items}


@router.post("", status_code=201)
async def create_treatment(
    body: TreatmentCreate,
    session: AsyncSession = Depends(get_session),
):
    svc = TreatmentService(session)
    audit_svc = AuditService(session)
    data = body.model_dump(exclude_none=True)
    if "event_date" in data:
        data["event_date"] = _parse_date(data.pop("event_date"))
    if "metadata" in data:
        data["metadata"] = data.pop("metadata")
    event = await svc.create_treatment(data)
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="create",
        resource_type="treatment",
        resource_id=str(event.id),
        details={"event_type": event.event_type, "patient_ref": event.patient_ref}
    )
    
    return svc._serialize(event)


@router.get("/timeline/{patient_ref}")
async def get_timeline(
    patient_ref: str,
    session: AsyncSession = Depends(get_session),
):
    svc = TreatmentService(session)
    events = await svc.get_timeline(patient_ref)
    return {"events": events}


@router.get("/{event_id}")
async def get_treatment(
    event_id: int,
    session: AsyncSession = Depends(get_session),
):
    svc = TreatmentService(session)
    event = await svc.get_treatment(event_id)
    if event is None:
        raise HTTPException(404, "Treatment event not found")
    return event


@router.put("/{event_id}")
async def update_treatment(
    event_id: int,
    body: TreatmentUpdate,
    session: AsyncSession = Depends(get_session),
):
    svc = TreatmentService(session)
    audit_svc = AuditService(session)
    data = body.model_dump(exclude_none=True)
    if "event_date" in data:
        data["event_date"] = _parse_date(data.pop("event_date"))
    if "metadata" in data:
        data["metadata"] = data.pop("metadata")
    event = await svc.update_treatment(event_id, data)
    if event is None:
        raise HTTPException(404, "Treatment event not found")
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="update",
        resource_type="treatment",
        resource_id=str(event.id),
        details={"event_type": event.event_type, "patient_ref": event.patient_ref}
    )
    
    return svc._serialize(event)


@router.delete("/{event_id}", status_code=204)
async def delete_treatment(
    event_id: int,
    session: AsyncSession = Depends(get_session),
):
    svc = TreatmentService(session)
    audit_svc = AuditService(session)
    
    # Get treatment info before deletion for audit
    event = await svc.get_treatment(event_id)
    if event is None:
        raise HTTPException(404, "Treatment event not found")
    
    ok = await svc.delete_treatment(event_id)
    if not ok:
        raise HTTPException(404, "Treatment event not found")
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="delete",
        resource_type="treatment",
        resource_id=str(event.id),
        details={"event_type": event.event_type, "patient_ref": event.patient_ref}
    )


# Also register the timeline route under /timeline prefix
timeline_router = APIRouter(prefix="/timeline", tags=["timeline"])


@timeline_router.get("/{patient_ref}")
async def get_timeline_short(
    patient_ref: str,
    session: AsyncSession = Depends(get_session),
):
    svc = TreatmentService(session)
    events = await svc.get_timeline(patient_ref)
    return {"events": events}
