"""Label management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.label_service import LabelService
from vna_main.services.audit_service import AuditService

router = APIRouter(prefix="/labels", tags=["labels"])


class LabelItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tag_key: str
    tag_value: str
    tag_type: str = "custom"
    tagged_by: str | None = None


class LabelsSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    labels: list[LabelItem]
    tagged_by: str | None = None


class LabelsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    labels: list[LabelItem]
    tagged_by: str | None = None


class BatchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str  # set | patch | remove
    resource_id: str
    labels: list[LabelItem] | None = None
    tag_key: str | None = None
    tag_value: str | None = None
    tagged_by: str | None = None


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operations: list[BatchOperation]


def _serialize_label(lbl) -> dict:
    return {
        "id": lbl.id,
        "resource_id": lbl.resource_id,
        "tag_key": lbl.tag_key,
        "tag_value": lbl.tag_value,
        "tag_type": lbl.tag_type,
        "tagged_by": lbl.tagged_by,
        "tagged_at": lbl.tagged_at.isoformat() if lbl.tagged_at else None,
    }


@router.get("")
async def list_labels(
    tag_type: str | None = None,
    search: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    svc = LabelService(session)
    items, total = await svc.list_labels(tag_type=tag_type, search=search, offset=offset, limit=limit)
    return {"total": total, "items": items}


@router.get("/resource/{resource_id}")
async def get_resource_labels(
    resource_id: str,
    session: AsyncSession = Depends(get_session),
):
    svc = LabelService(session)
    labels = await svc.get_resource_labels(resource_id)
    return {"resource_id": resource_id, "labels": [_serialize_label(l) for l in labels]}


@router.put("/resource/{resource_id}")
async def set_resource_labels(
    resource_id: str,
    body: LabelsSet,
    session: AsyncSession = Depends(get_session),
):
    svc = LabelService(session)
    audit_svc = AuditService(session)
    labels_data = [l.model_dump() for l in body.labels]
    labels = await svc.set_labels(resource_id, labels_data, tagged_by=body.tagged_by)
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="set",
        resource_type="label",
        resource_id=resource_id,
        details={"label_count": len(labels_data), "tagged_by": body.tagged_by}
    )
    
    return {"resource_id": resource_id, "labels": [_serialize_label(l) for l in labels]}


@router.patch("/resource/{resource_id}")
async def patch_resource_labels(
    resource_id: str,
    body: LabelsPatch,
    session: AsyncSession = Depends(get_session),
):
    svc = LabelService(session)
    audit_svc = AuditService(session)
    labels_data = [l.model_dump() for l in body.labels]
    labels = await svc.patch_labels(resource_id, labels_data, tagged_by=body.tagged_by)
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="patch",
        resource_type="label",
        resource_id=resource_id,
        details={"label_count": len(labels_data), "tagged_by": body.tagged_by}
    )
    
    return {"resource_id": resource_id, "labels": [_serialize_label(l) for l in labels]}


@router.post("/batch")
async def batch_labels(
    body: BatchRequest,
    session: AsyncSession = Depends(get_session),
):
    svc = LabelService(session)
    audit_svc = AuditService(session)
    ops = []
    for op in body.operations:
        d = op.model_dump(exclude_none=True)
        if d.get("labels"):
            d["labels"] = [l.model_dump() for l in op.labels] if op.labels else []
        ops.append(d)
    result = await svc.batch_label(ops)
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="batch",
        resource_type="label",
        resource_id="batch",
        details={"operation_count": len(ops), "operations": [op.action for op in body.operations]}
    )
    
    return result


@router.get("/history")
async def get_label_history(
    resource_id: str | None = None,
    tag_key: str | None = None,
    action: str | None = None,
    tagged_by: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    svc = LabelService(session)
    items, total = await svc.get_label_history(
        resource_id=resource_id,
        tag_key=tag_key,
        action=action,
        tagged_by=tagged_by,
        offset=offset,
        limit=limit,
    )
    return {
        "total": total,
        "items": [
            {
                "id": h.id,
                "resource_id": h.resource_id,
                "tag_key": h.tag_key,
                "tag_value": h.tag_value,
                "tag_type": h.tag_type,
                "action": h.action,
                "tagged_by": h.tagged_by,
                "tagged_at": h.tagged_at.isoformat() if h.tagged_at else None,
            }
            for h in items
        ],
    }
