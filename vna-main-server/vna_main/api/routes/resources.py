"""Resource index API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.resource_service import ResourceService
from vna_main.services.audit_service import AuditService

router = APIRouter(prefix="/resources", tags=["resources"])


# --- Schemas ---

class ResourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_id: str | None = None
    patient_ref: str | None = None
    source_type: str = "dicom_only"
    dicom_study_uid: str | None = None
    dicom_series_uid: str | None = None
    dicom_sop_uid: str | None = None
    bids_subject_id: str | None = None
    bids_session_id: str | None = None
    bids_path: str | None = None
    data_type: str = "dicom"
    file_name: str | None = None
    file_size: int | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] | None = None


class ResourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_ref: str | None = None
    source_type: str | None = None
    dicom_study_uid: str | None = None
    dicom_series_uid: str | None = None
    dicom_sop_uid: str | None = None
    bids_subject_id: str | None = None
    bids_session_id: str | None = None
    bids_path: str | None = None
    data_type: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] | None = None


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resource_id: str
    patient_ref: str | None = None
    source_type: str
    dicom_study_uid: str | None = None
    dicom_series_uid: str | None = None
    dicom_sop_uid: str | None = None
    bids_subject_id: str | None = None
    bids_session_id: str | None = None
    bids_path: str | None = None
    data_type: str
    file_name: str | None = None
    file_size: int | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None


def _serialize(r) -> dict:
    if isinstance(r, dict):
        return r
    return {
        "resource_id": r.resource_id,
        "patient_ref": r.patient_ref,
        "source_type": r.source_type,
        "dicom_study_uid": r.dicom_study_uid,
        "dicom_series_uid": r.dicom_series_uid,
        "dicom_sop_uid": r.dicom_sop_uid,
        "bids_subject_id": r.bids_subject_id,
        "bids_session_id": r.bids_session_id,
        "bids_path": r.bids_path,
        "data_type": r.data_type,
        "file_name": r.file_name,
        "file_size": r.file_size,
        "content_hash": r.content_hash,
        "metadata": r.metadata_,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("")
async def list_resources(
    patient_ref: str | None = None,
    source_type: str | None = None,
    data_type: str | None = None,
    dicom_study_uid: str | None = None,
    bids_subject_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    svc = ResourceService(session)
    items, total = await svc.list_resources(
        patient_ref=patient_ref,
        source_type=source_type,
        data_type=data_type,
        dicom_study_uid=dicom_study_uid,
        bids_subject_id=bids_subject_id,
        offset=offset,
        limit=limit,
    )
    return {"total": total, "items": [_serialize(r) for r in items]}


@router.get("/{resource_id}")
async def get_resource(
    resource_id: str,
    session: AsyncSession = Depends(get_session),
):
    svc = ResourceService(session)
    resource = await svc.get_resource(resource_id)
    if resource is None:
        raise HTTPException(404, "Resource not found")
    return _serialize(resource)


@router.post("", status_code=201)
async def create_resource(
    body: ResourceCreate,
    session: AsyncSession = Depends(get_session),
):
    svc = ResourceService(session)
    audit_svc = AuditService(session)
    data = body.model_dump(exclude_none=True)
    if "metadata" in data:
        data["metadata"] = data.pop("metadata")
    resource = await svc.create_resource(data)
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="create",
        resource_type="resource",
        resource_id=resource.resource_id,
        details={"source_type": resource.source_type, "data_type": resource.data_type}
    )
    
    return _serialize(resource)


async def _update_resource(
    resource_id: str,
    body: ResourceUpdate,
    session: AsyncSession = Depends(get_session),
):
    svc = ResourceService(session)
    audit_svc = AuditService(session)
    data = body.model_dump(exclude_none=True)
    if "metadata" in data:
        data["metadata"] = data.pop("metadata")
    resource = await svc.update_resource(resource_id, data)
    if resource is None:
        raise HTTPException(404, "Resource not found")
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="update",
        resource_type="resource",
        resource_id=resource.resource_id,
        details={"updated_fields": list(data.keys())}
    )
    
    return _serialize(resource)


@router.put("/{resource_id}")
async def update_resource(
    resource_id: str,
    body: ResourceUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await _update_resource(resource_id, body, session)


@router.patch("/{resource_id}")
async def patch_resource(
    resource_id: str,
    body: ResourceUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await _update_resource(resource_id, body, session)


@router.delete("/{resource_id}")
async def delete_resource(
    resource_id: str,
    session: AsyncSession = Depends(get_session),
):
    svc = ResourceService(session)
    audit_svc = AuditService(session)
    
    # Get resource info before deletion for audit
    resource = await svc.get_resource(resource_id)
    if resource is None:
        raise HTTPException(404, "Resource not found")
    resource_data = _serialize(resource)
    
    ok = await svc.delete_resource(resource_id)
    if not ok:
        raise HTTPException(404, "Resource not found")
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="delete",
        resource_type="resource",
        resource_id=resource_id,
        details={
            "source_type": resource_data["source_type"],
            "data_type": resource_data["data_type"],
        }
    )
    
    return {"deleted": resource_id}
