"""Annotations API - Structured annotation management."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import Annotation
from bids_server.models.schemas import AnnotationCreate, AnnotationUpdate, AnnotationResponse
from bids_server.core.webhook_manager import webhook_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bidsweb/v1/annotations", tags=["Annotations"])


@router.get("", response_model=list[AnnotationResponse])
async def list_annotations(
    resource_id: Optional[str] = None,
    ann_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List annotations with optional filters."""
    query = select(Annotation).order_by(Annotation.created_at.desc())
    if resource_id:
        query = query.where(Annotation.resource_id == resource_id)
    if ann_type:
        query = query.where(Annotation.ann_type == ann_type)
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return [AnnotationResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(annotation_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific annotation."""
    result = await db.execute(
        select(Annotation).where(Annotation.annotation_id == annotation_id)
    )
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(404, f"Annotation {annotation_id} not found")
    return AnnotationResponse.model_validate(ann)


@router.post("", response_model=AnnotationResponse, status_code=201)
async def create_annotation(req: AnnotationCreate, db: AsyncSession = Depends(get_db)):
    """Create a new annotation."""
    ann = Annotation(
        resource_id=req.resource_id,
        ann_type=req.ann_type,
        label=req.label,
        data=req.data,
        confidence=req.confidence,
        created_by=req.created_by,
    )
    db.add(ann)
    await db.commit()
    result = AnnotationResponse.model_validate(ann)

    try:
        await webhook_manager.dispatch(
            "annotation.created",
            {"annotation_id": ann.annotation_id, "resource_id": req.resource_id},
            req.resource_id,
        )
    except Exception as exc:
        logger.warning("Webhook dispatch failed: %s", exc)
    return result


@router.put("/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(annotation_id: str, req: AnnotationUpdate, db: AsyncSession = Depends(get_db)):
    """Update an annotation."""
    result = await db.execute(
        select(Annotation).where(Annotation.annotation_id == annotation_id)
    )
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(404, f"Annotation {annotation_id} not found")
    if req.label is not None:
        ann.label = req.label
    if req.data is not None:
        ann.data = req.data
    if req.confidence is not None:
        ann.confidence = req.confidence
    await db.commit()
    return AnnotationResponse.model_validate(ann)


@router.delete("/{annotation_id}")
async def delete_annotation(annotation_id: str, db: AsyncSession = Depends(get_db)):
    """Delete an annotation."""
    result = await db.execute(
        select(Annotation).where(Annotation.annotation_id == annotation_id)
    )
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(404, f"Annotation {annotation_id} not found")
    await db.delete(ann)
    await db.commit()
    return {"deleted": True, "annotation_id": annotation_id}
