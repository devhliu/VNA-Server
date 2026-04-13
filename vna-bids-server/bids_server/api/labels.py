"""Labels API - Tag management with JSON sync."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.schemas import LabelSet, LabelPatch, LabelResponse
from bids_server.services.label_service import label_service
from bids_server.core.webhook_manager import webhook_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bidsweb/v1/labels", tags=["Labels"])


@router.get("", response_model=list[dict])
async def list_all_tags(db: AsyncSession = Depends(get_db)):
    """List all unique tags with counts."""
    return await label_service.get_all_tags(db)


@router.get("/{resource_id}", response_model=list[LabelResponse])
async def get_labels(resource_id: str, db: AsyncSession = Depends(get_db)):
    """Get all labels for a resource."""
    labels = await label_service.get_labels(db, resource_id)
    return [LabelResponse.model_validate(l) for l in labels]


@router.put("/{resource_id}", response_model=list[LabelResponse])
async def set_labels(resource_id: str, req: LabelSet, db: AsyncSession = Depends(get_db)):
    """Replace all labels on a resource."""
    labels = await label_service.set_labels(
        db, resource_id, req.labels, level=req.level, target_path=req.target_path,
    )
    await db.commit()
    result = [LabelResponse.model_validate(l) for l in labels]

    try:
        await webhook_manager.dispatch(
            "label.updated",
            {"resource_id": resource_id, "action": "set", "labels": req.labels},
            resource_id,
        )
    except Exception as exc:
        logger.warning("Webhook dispatch failed: %s", exc)
    return result


@router.patch("/{resource_id}", response_model=list[LabelResponse])
async def patch_labels(resource_id: str, req: LabelPatch, db: AsyncSession = Depends(get_db)):
    """Add/update/remove specific labels."""
    labels = await label_service.patch_labels(
        db, resource_id, add=req.add, remove=req.remove,
    )
    await db.commit()
    result = [LabelResponse.model_validate(l) for l in labels]

    try:
        await webhook_manager.dispatch(
            "label.updated",
            {"resource_id": resource_id, "action": "patch"},
            resource_id,
        )
    except Exception as exc:
        logger.warning("Webhook dispatch failed: %s", exc)
    return result
