"""Data version management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.version_service import VersionService
from vna_main.services.audit_service import AuditService


router = APIRouter(prefix="/versions", tags=["versions"])


class CreateSnapshotRequest(BaseModel):
    name: str
    description: str | None = None
    snapshot_type: str = "manual"
    created_by: str | None = None
    filters: dict[str, Any] | None = None


class CreateVersionRequest(BaseModel):
    change_type: str = "update"
    change_description: str | None = None
    changed_by: str | None = None


@router.get("/resources/{resource_id}/versions")
async def list_resource_versions(
    resource_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = VersionService(db)
    versions, total = await svc.list_versions(resource_id, limit=limit, offset=offset)
    return {"resource_id": resource_id, "versions": versions, "total": total}


@router.get("/resources/{resource_id}/versions/{version_number}")
async def get_resource_version(
    resource_id: str,
    version_number: int,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = VersionService(db)
    version = await svc.get_version(resource_id, version_number)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/resources/{resource_id}/versions")
async def create_resource_version(
    resource_id: str,
    request: CreateVersionRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = VersionService(db)
    audit_svc = AuditService(db)
    version = await svc.create_version(
        resource_id=resource_id,
        change_type=request.change_type,
        change_description=request.change_description,
        changed_by=request.changed_by,
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    await db.commit()
    
    # Audit log
    await audit_svc.log(
        action="create",
        resource_type="version",
        resource_id=str(version.id),
        details={
            "resource_id": version.resource_id,
            "version_number": version.version_number,
            "change_type": version.change_type,
            "changed_by": version.changed_by
        }
    )
    
    return {
        "id": version.id,
        "resource_id": version.resource_id,
        "version_number": version.version_number,
        "change_type": version.change_type,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


@router.post("/resources/{resource_id}/versions/{version_number}/restore")
async def restore_resource_version(
    resource_id: str,
    version_number: int,
    restored_by: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = VersionService(db)
    audit_svc = AuditService(db)
    result = await svc.restore_version(
        resource_id=resource_id,
        version_number=version_number,
        restored_by=restored_by,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Restore failed"))
    await db.commit()
    
    # Audit log
    await audit_svc.log(
        action="restore",
        resource_type="version",
        resource_id=resource_id,
        details={
            "version_number": version_number,
            "restored_by": restored_by,
            "success": result.get("success"),
            "resource_count": result.get("resource_count", 0)
        }
    )
    
    return result


@router.get("/resources/{resource_id}/versions/{version1}/compare/{version2}")
async def compare_resource_versions(
    resource_id: str,
    version1: int,
    version2: int,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = VersionService(db)
    result = await svc.compare_versions(resource_id, version1, version2)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/snapshots")
async def list_snapshots(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = VersionService(db)
    snapshots, total = await svc.list_snapshots(limit=limit, offset=offset)
    return {"snapshots": snapshots, "total": total}


@router.post("/snapshots")
async def create_snapshot(
    request: CreateSnapshotRequest,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = VersionService(db)
    snapshot = await svc.create_snapshot(
        name=request.name,
        description=request.description,
        snapshot_type=request.snapshot_type,
        created_by=request.created_by,
        filters=request.filters,
    )
    await db.commit()
    return {
        "id": snapshot.id,
        "snapshot_id": snapshot.snapshot_id,
        "name": snapshot.name,
        "resource_count": snapshot.resource_count,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(
    snapshot_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = VersionService(db)
    snapshot = await svc.get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(
    snapshot_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = VersionService(db)
    deleted = await svc.delete_snapshot(snapshot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    await db.commit()
    return {"deleted": True, "snapshot_id": snapshot_id}
