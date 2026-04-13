"""Resource index management service with caching."""

from __future__ import annotations

import json
import hashlib
import logging
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import ResourceIndex, _make_resource_id
from vna_main.services.cache_service import get_cache, CacheKeys

logger = logging.getLogger(__name__)


class ResourceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._cache = get_cache()
    
    def _make_query_cache_key(self, **filters) -> str:
        filter_str = json.dumps(filters, sort_keys=True, default=str)
        query_hash = hashlib.sha256(filter_str.encode()).hexdigest()[:12]
        return f"query:resources:{query_hash}"

    async def list_resources(
        self,
        *,
        patient_ref: str | None = None,
        source_type: str | None = None,
        data_type: str | None = None,
        dicom_study_uid: str | None = None,
        bids_subject_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
        use_cache: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        """List resources with optional filters. Returns (items, total_count)."""
        cache_key = self._make_query_cache_key(
            patient_ref=patient_ref,
            source_type=source_type,
            data_type=data_type,
            dicom_study_uid=dicom_study_uid,
            bids_subject_id=bids_subject_id,
            offset=offset,
            limit=limit,
        )
        
        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached["items"], cached["total"]
        
        stmt = select(ResourceIndex)
        count_stmt = select(func.count()).select_from(ResourceIndex)

        if patient_ref:
            stmt = stmt.where(ResourceIndex.patient_ref == patient_ref)
            count_stmt = count_stmt.where(ResourceIndex.patient_ref == patient_ref)
        if source_type:
            stmt = stmt.where(ResourceIndex.source_type == source_type)
            count_stmt = count_stmt.where(ResourceIndex.source_type == source_type)
        if data_type:
            stmt = stmt.where(ResourceIndex.data_type == data_type)
            count_stmt = count_stmt.where(ResourceIndex.data_type == data_type)
        if dicom_study_uid:
            stmt = stmt.where(ResourceIndex.dicom_study_uid == dicom_study_uid)
            count_stmt = count_stmt.where(ResourceIndex.dicom_study_uid == dicom_study_uid)
        if bids_subject_id:
            stmt = stmt.where(ResourceIndex.bids_subject_id == bids_subject_id)
            count_stmt = count_stmt.where(ResourceIndex.bids_subject_id == bids_subject_id)

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.offset(offset).limit(limit).order_by(ResourceIndex.created_at.desc())
        result = await self.session.execute(stmt)
        items = [
            {
                "resource_id": r.resource_id,
                "patient_ref": r.patient_ref,
                "source_type": r.source_type,
                "data_type": r.data_type,
                "dicom_study_uid": r.dicom_study_uid,
                "dicom_series_uid": r.dicom_series_uid,
                "dicom_sop_uid": r.dicom_sop_uid,
                "bids_subject_id": r.bids_subject_id,
                "bids_session_id": r.bids_session_id,
                "bids_path": r.bids_path,
                "file_name": r.file_name,
                "file_size": r.file_size,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in result.scalars().all()
        ]
        
        if use_cache:
            await self._cache.set(cache_key, {"items": items, "total": total}, ttl=60)
        
        return items, total

    async def get_resource(self, resource_id: str, use_cache: bool = True) -> dict[str, Any] | None:
        cache_key = CacheKeys.resource_key(resource_id)
        
        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached
        
        resource = await self.session.get(ResourceIndex, resource_id)
        if resource is None:
            return None
        
        result = {
            "resource_id": resource.resource_id,
            "patient_ref": resource.patient_ref,
            "source_type": resource.source_type,
            "data_type": resource.data_type,
            "dicom_study_uid": resource.dicom_study_uid,
            "dicom_series_uid": resource.dicom_series_uid,
            "dicom_sop_uid": resource.dicom_sop_uid,
            "bids_subject_id": resource.bids_subject_id,
            "bids_session_id": resource.bids_session_id,
            "bids_path": resource.bids_path,
            "file_name": resource.file_name,
            "file_size": resource.file_size,
            "content_hash": resource.content_hash,
            "metadata": resource.metadata_,
            "created_at": resource.created_at.isoformat() if resource.created_at else None,
        }
        
        if use_cache:
            await self._cache.set(cache_key, result, ttl=300)
        
        return result

    async def create_resource(self, data: dict[str, Any]) -> ResourceIndex:
        resource_id = data.get("resource_id") or _make_resource_id()
        resource = ResourceIndex(
            resource_id=resource_id,
            patient_ref=data.get("patient_ref"),
            source_type=data.get("source_type", "dicom_only"),
            dicom_study_uid=data.get("dicom_study_uid"),
            dicom_series_uid=data.get("dicom_series_uid"),
            dicom_sop_uid=data.get("dicom_sop_uid"),
            bids_subject_id=data.get("bids_subject_id"),
            bids_session_id=data.get("bids_session_id"),
            bids_path=data.get("bids_path"),
            data_type=data.get("data_type", "dicom"),
            file_name=data.get("file_name"),
            file_size=data.get("file_size"),
            content_hash=data.get("content_hash"),
            metadata_=data.get("metadata"),
        )
        self.session.add(resource)
        await self.session.flush()
        
        await self._cache.delete(CacheKeys.resource_key(resource_id))
        await self._cache.clear_pattern("query:resources:*")
        
        return resource

    async def update_resource(self, resource_id: str, data: dict[str, Any]) -> ResourceIndex | None:
        resource = await self.session.get(ResourceIndex, resource_id)
        if resource is None:
            return None
        updatable_fields = {"source_type", "data_type", "patient_ref", "dicom_study_uid", "bids_path", "metadata_"}
        for key, value in data.items():
            if key == "metadata":
                key = "metadata_"
            if key in updatable_fields:
                setattr(resource, key, value)
        await self.session.flush()
        
        await self._cache.delete(CacheKeys.resource_key(resource_id))
        await self._cache.clear_pattern("query:resources:*")
        
        return resource

    async def delete_resource(self, resource_id: str) -> bool:
        resource = await self.session.get(ResourceIndex, resource_id)
        if resource is None:
            return False
        await self.session.delete(resource)
        await self.session.flush()
        
        await self._cache.delete(CacheKeys.resource_key(resource_id))
        await self._cache.clear_pattern("query:resources:*")
        
        return True
    
    async def invalidate_cache(self, resource_id: str | None = None) -> None:
        if resource_id:
            await self._cache.delete(CacheKeys.resource_key(resource_id))
        await self._cache.clear_pattern("query:resources:*")
