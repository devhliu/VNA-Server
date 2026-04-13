"""Audit log API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def list_audit_logs(
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    actor: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = AuditService(session)
    items, total = await svc.list_logs(
        action=action, resource_type=resource_type,
        resource_id=resource_id, actor=actor,
        offset=offset, limit=limit,
    )
    return {
        "items": [
            {"id": e.id, "actor": e.actor, "action": e.action,
             "resource_type": e.resource_type, "resource_id": e.resource_id,
             "details": e.details,
             "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in items
        ],
        "total": total,
    }
