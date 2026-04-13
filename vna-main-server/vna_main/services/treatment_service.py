"""Treatment event service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import TreatmentEvent


class TreatmentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_treatments(
        self,
        *,
        patient_ref: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(TreatmentEvent)
        count_stmt = select(func.count()).select_from(TreatmentEvent)

        if patient_ref:
            stmt = stmt.where(TreatmentEvent.patient_ref == patient_ref)
            count_stmt = count_stmt.where(TreatmentEvent.patient_ref == patient_ref)

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.offset(offset).limit(limit).order_by(TreatmentEvent.created_at.desc())
        result = await self.session.execute(stmt)
        items = [self._serialize(e) for e in result.scalars().all()]
        return items, total

    async def get_treatment(self, event_id: int) -> dict[str, Any] | None:
        event = await self.session.get(TreatmentEvent, event_id)
        if event is None:
            return None
        return self._serialize(event)

    async def create_treatment(self, data: dict[str, Any]) -> TreatmentEvent:
        event = TreatmentEvent(**data)
        self.session.add(event)
        await self.session.flush()
        return event

    async def update_treatment(self, event_id: int, data: dict[str, Any]) -> TreatmentEvent | None:
        event = await self.session.get(TreatmentEvent, event_id)
        if event is None:
            return None
        updatable_fields = {"patient_ref", "event_type", "event_date", "description", "outcome", "facility", "metadata_"}
        for key, value in data.items():
            if key == "metadata":
                key = "metadata_"
            if key in updatable_fields:
                setattr(event, key, value)
        await self.session.flush()
        return event

    async def delete_treatment(self, event_id: int) -> bool:
        event = await self.session.get(TreatmentEvent, event_id)
        if event is None:
            return False
        await self.session.delete(event)
        await self.session.flush()
        return True

    async def get_timeline(self, patient_ref: str) -> list[dict[str, Any]]:
        stmt = (
            select(TreatmentEvent)
            .where(TreatmentEvent.patient_ref == patient_ref)
            .order_by(TreatmentEvent.event_date.asc())
        )
        result = await self.session.execute(stmt)
        return [self._serialize(e) for e in result.scalars().all()]

    @staticmethod
    def _serialize(e: TreatmentEvent) -> dict[str, Any]:
        return {
            "id": e.id,
            "patient_ref": e.patient_ref,
            "event_type": e.event_type,
            "event_date": e.event_date.isoformat() if e.event_date else None,
            "description": e.description,
            "outcome": e.outcome,
            "facility": e.facility,
            "metadata": e.metadata_,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
