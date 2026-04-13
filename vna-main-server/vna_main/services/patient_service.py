"""Patient ID mapping service with caching."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vna_main.models.database import PatientMapping, _make_patient_ref
from vna_main.services.cache_service import get_cache, CacheKeys

logger = logging.getLogger(__name__)


class PatientService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._cache = get_cache()

    async def list_patients(
        self,
        *,
        source: str | None = None,
        hospital_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
        use_cache: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        cache_key = f"patients:list:{source or 'all'}:{hospital_id or 'all'}:{offset}:{limit}"
        
        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached["items"], cached["total"]
        
        stmt = select(PatientMapping).options(selectinload(PatientMapping.resources))
        count_stmt = select(func.count()).select_from(PatientMapping)

        if source:
            stmt = stmt.where(PatientMapping.source == source)
            count_stmt = count_stmt.where(PatientMapping.source == source)
        if hospital_id:
            stmt = stmt.where(PatientMapping.hospital_id == hospital_id)
            count_stmt = count_stmt.where(PatientMapping.hospital_id == hospital_id)

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.offset(offset).limit(limit).order_by(PatientMapping.created_at.desc())
        result = await self.session.execute(stmt)
        items = [
            {
                "patient_ref": p.patient_ref,
                "hospital_id": p.hospital_id,
                "source": p.source,
                "external_system": p.external_system,
                "resource_count": len(p.resources) if p.resources else 0,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in result.scalars().all()
        ]
        
        if use_cache:
            await self._cache.set(cache_key, {"items": items, "total": total}, ttl=60)
        
        return items, total

    async def get_patient(self, patient_ref: str, use_cache: bool = True) -> dict[str, Any] | None:
        cache_key = CacheKeys.patient_key(patient_ref)
        
        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached:
                return cached
        
        stmt = (
            select(PatientMapping)
            .where(PatientMapping.patient_ref == patient_ref)
            .options(selectinload(PatientMapping.resources))
        )
        result = await self.session.execute(stmt)
        patient = result.scalar_one_or_none()
        
        if patient is None:
            return None
        
        data = {
            "patient_ref": patient.patient_ref,
            "hospital_id": patient.hospital_id,
            "source": patient.source,
            "external_system": patient.external_system,
            "resource_count": len(patient.resources) if patient.resources else 0,
            "resources": [
                {
                    "resource_id": r.resource_id,
                    "source_type": r.source_type,
                    "data_type": r.data_type,
                }
                for r in patient.resources
            ],
            "created_at": patient.created_at.isoformat() if patient.created_at else None,
        }
        
        if use_cache:
            await self._cache.set(cache_key, data, ttl=300)
        
        return data

    async def create_patient(self, data: dict[str, Any]) -> PatientMapping:
        patient_ref = data.get("patient_ref") or _make_patient_ref()
        patient = PatientMapping(
            patient_ref=patient_ref,
            hospital_id=data["hospital_id"],
            source=data["source"],
            external_system=data.get("external_system"),
        )
        self.session.add(patient)
        await self.session.flush()
        
        await self._cache.clear_pattern("patients:list:*")
        
        return patient

    async def update_patient(self, patient_ref: str, data: dict[str, Any]) -> PatientMapping | None:
        patient = await self.session.get(PatientMapping, patient_ref)
        if patient is None:
            return None
        updatable_fields = {"hospital_id", "source", "external_system"}
        for key, value in data.items():
            if key in updatable_fields:
                setattr(patient, key, value)
        await self.session.flush()
        
        await self._cache.delete(CacheKeys.patient_key(patient_ref))
        await self._cache.clear_pattern("patients:list:*")
        
        return patient

    async def delete_patient(self, patient_ref: str) -> bool:
        patient = await self.session.get(PatientMapping, patient_ref)
        if patient is None:
            return False
        await self.session.delete(patient)
        await self.session.flush()
        
        await self._cache.delete(CacheKeys.patient_key(patient_ref))
        await self._cache.clear_pattern("patients:list:*")
        
        return True
    
    async def invalidate_cache(self, patient_ref: str | None = None) -> None:
        if patient_ref:
            await self._cache.delete(CacheKeys.patient_key(patient_ref))
        await self._cache.clear_pattern("patients:list:*")
