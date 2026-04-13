"""Data version management service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import (
    ResourceIndex,
    ResourceVersion,
    DataSnapshot,
    Label,
)

logger = logging.getLogger(__name__)


class VersionService:
    """Service for managing resource versions and data snapshots."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_version(
        self,
        resource_id: str,
        change_type: str = "update",
        change_description: str | None = None,
        changed_by: str | None = None,
    ) -> ResourceVersion | None:
        resource = await self.session.get(ResourceIndex, resource_id)
        if resource is None:
            return None
        
        version_stmt = (
            select(func.max(ResourceVersion.version_number))
            .where(ResourceVersion.resource_id == resource_id)
        )
        result = await self.session.execute(version_stmt)
        max_version = result.scalar() or 0
        
        labels_stmt = select(Label).where(Label.resource_id == resource_id)
        labels_result = await self.session.execute(labels_stmt)
        labels = [
            {
                "tag_key": l.tag_key,
                "tag_value": l.tag_value,
                "tag_type": l.tag_type,
                "tagged_by": l.tagged_by,
            }
            for l in labels_result.scalars().all()
        ]
        
        snapshot = {
            "resource_id": resource.resource_id,
            "patient_ref": resource.patient_ref,
            "source_type": resource.source_type,
            "dicom_study_uid": resource.dicom_study_uid,
            "dicom_series_uid": resource.dicom_series_uid,
            "dicom_sop_uid": resource.dicom_sop_uid,
            "bids_subject_id": resource.bids_subject_id,
            "bids_session_id": resource.bids_session_id,
            "bids_path": resource.bids_path,
            "data_type": resource.data_type,
            "file_name": resource.file_name,
            "file_size": resource.file_size,
            "content_hash": resource.content_hash,
            "metadata": resource.metadata_,
            "labels": labels,
        }
        
        version = ResourceVersion(
            resource_id=resource_id,
            version_number=max_version + 1,
            snapshot=snapshot,
            change_type=change_type,
            change_description=change_description,
            changed_by=changed_by,
        )
        self.session.add(version)
        await self.session.flush()
        return version
    
    async def get_version(self, resource_id: str, version_number: int) -> dict[str, Any] | None:
        stmt = (
            select(ResourceVersion)
            .where(
                and_(
                    ResourceVersion.resource_id == resource_id,
                    ResourceVersion.version_number == version_number,
                )
            )
        )
        result = await self.session.execute(stmt)
        version = result.scalar_one_or_none()
        if version is None:
            return None
        
        return {
            "id": version.id,
            "resource_id": version.resource_id,
            "version_number": version.version_number,
            "snapshot": version.snapshot,
            "change_type": version.change_type,
            "change_description": version.change_description,
            "changed_by": version.changed_by,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }
    
    async def list_versions(
        self,
        resource_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        count_stmt = (
            select(func.count())
            .select_from(ResourceVersion)
            .where(ResourceVersion.resource_id == resource_id)
        )
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        stmt = (
            select(ResourceVersion)
            .where(ResourceVersion.resource_id == resource_id)
            .order_by(ResourceVersion.version_number.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        versions = [
            {
                "id": v.id,
                "resource_id": v.resource_id,
                "version_number": v.version_number,
                "change_type": v.change_type,
                "change_description": v.change_description,
                "changed_by": v.changed_by,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in result.scalars().all()
        ]
        return versions, total
    
    async def restore_version(
        self,
        resource_id: str,
        version_number: int,
        restored_by: str | None = None,
    ) -> dict[str, Any]:
        version_data = await self.get_version(resource_id, version_number)
        if version_data is None:
            return {"success": False, "error": "version_not_found"}
        
        resource = await self.session.get(ResourceIndex, resource_id)
        if resource is None:
            return {"success": False, "error": "resource_not_found"}
        
        snapshot = version_data["snapshot"]
        
        await self.create_version(
            resource_id=resource_id,
            change_type="pre_restore",
            change_description=f"Auto-backup before restoring version {version_number}",
            changed_by=restored_by,
        )
        
        resource.patient_ref = snapshot.get("patient_ref")
        resource.source_type = snapshot.get("source_type", "dicom_only")
        resource.dicom_study_uid = snapshot.get("dicom_study_uid")
        resource.dicom_series_uid = snapshot.get("dicom_series_uid")
        resource.dicom_sop_uid = snapshot.get("dicom_sop_uid")
        resource.bids_subject_id = snapshot.get("bids_subject_id")
        resource.bids_session_id = snapshot.get("bids_session_id")
        resource.bids_path = snapshot.get("bids_path")
        resource.data_type = snapshot.get("data_type", "dicom")
        resource.file_name = snapshot.get("file_name")
        resource.file_size = snapshot.get("file_size")
        resource.content_hash = snapshot.get("content_hash")
        resource.metadata_ = snapshot.get("metadata")
        
        await self.session.flush()
        
        await self.create_version(
            resource_id=resource_id,
            change_type="restore",
            change_description=f"Restored from version {version_number}",
            changed_by=restored_by,
        )
        
        return {
            "success": True,
            "resource_id": resource_id,
            "restored_from_version": version_number,
        }
    
    async def compare_versions(
        self,
        resource_id: str,
        version1: int,
        version2: int,
    ) -> dict[str, Any]:
        v1_data = await self.get_version(resource_id, version1)
        v2_data = await self.get_version(resource_id, version2)
        
        if v1_data is None or v2_data is None:
            return {"error": "version_not_found"}
        
        s1 = v1_data["snapshot"]
        s2 = v2_data["snapshot"]
        
        diff = {}
        all_keys = set(s1.keys()) | set(s2.keys())
        
        for key in all_keys:
            if key == "labels":
                continue
            v1_val = s1.get(key)
            v2_val = s2.get(key)
            if v1_val != v2_val:
                diff[key] = {
                    "version1": v1_val,
                    "version2": v2_val,
                }
        
        labels1 = {l["tag_key"]: l["tag_value"] for l in s1.get("labels", [])}
        labels2 = {l["tag_key"]: l["tag_value"] for l in s2.get("labels", [])}
        
        label_diff = {}
        all_label_keys = set(labels1.keys()) | set(labels2.keys())
        for key in all_label_keys:
            if labels1.get(key) != labels2.get(key):
                label_diff[key] = {
                    "version1": labels1.get(key),
                    "version2": labels2.get(key),
                }
        
        if label_diff:
            diff["labels"] = label_diff
        
        return {
            "resource_id": resource_id,
            "version1": version1,
            "version2": version2,
            "diff": diff,
            "has_changes": bool(diff),
        }
    
    async def create_snapshot(
        self,
        name: str,
        description: str | None = None,
        snapshot_type: str = "manual",
        created_by: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> DataSnapshot:
        stmt = select(ResourceIndex)
        if filters:
            if filters.get("patient_ref"):
                stmt = stmt.where(ResourceIndex.patient_ref == filters["patient_ref"])
            if filters.get("source_type"):
                stmt = stmt.where(ResourceIndex.source_type == filters["source_type"])
            if filters.get("data_type"):
                stmt = stmt.where(ResourceIndex.data_type == filters["data_type"])
        
        result = await self.session.execute(stmt)
        resources = result.scalars().all()
        
        snapshot = DataSnapshot(
            name=name,
            description=description,
            snapshot_type=snapshot_type,
            resource_count=len(resources),
            metadata_={"filters": filters} if filters else None,
            created_by=created_by,
        )
        self.session.add(snapshot)
        await self.session.flush()
        
        for resource in resources:
            await self.create_version(
                resource_id=resource.resource_id,
                change_type="snapshot",
                change_description=f"Snapshot: {name}",
                changed_by=created_by,
            )
        
        return snapshot
    
    async def list_snapshots(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        count_stmt = select(func.count()).select_from(DataSnapshot)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        stmt = (
            select(DataSnapshot)
            .order_by(DataSnapshot.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        snapshots = [
            {
                "id": s.id,
                "snapshot_id": s.snapshot_id,
                "name": s.name,
                "description": s.description,
                "snapshot_type": s.snapshot_type,
                "resource_count": s.resource_count,
                "created_by": s.created_by,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in result.scalars().all()
        ]
        return snapshots, total
    
    async def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        stmt = select(DataSnapshot).where(DataSnapshot.snapshot_id == snapshot_id)
        result = await self.session.execute(stmt)
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            return None
        
        return {
            "id": snapshot.id,
            "snapshot_id": snapshot.snapshot_id,
            "name": snapshot.name,
            "description": snapshot.description,
            "snapshot_type": snapshot.snapshot_type,
            "resource_count": snapshot.resource_count,
            "metadata": snapshot.metadata_,
            "created_by": snapshot.created_by,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }
    
    async def delete_snapshot(self, snapshot_id: str) -> bool:
        stmt = select(DataSnapshot).where(DataSnapshot.snapshot_id == snapshot_id)
        result = await self.session.execute(stmt)
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            return False
        
        await self.session.delete(snapshot)
        await self.session.flush()
        return True
