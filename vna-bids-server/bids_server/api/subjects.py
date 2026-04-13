"""Subjects API - Patient/subject management."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import Subject
from bids_server.models.schemas import SubjectCreate, SubjectUpdate, SubjectResponse

router = APIRouter(prefix="/bidsweb/v1/subjects", tags=["Subjects"])


@router.get("")
async def list_subjects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all subjects with pagination."""
    count_stmt = select(func.count()).select_from(Subject)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    result = await db.execute(
        select(Subject).order_by(Subject.subject_id).limit(limit).offset(offset)
    )
    items = [SubjectResponse.model_validate(s) for s in result.scalars().all()]
    
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get subject details."""
    result = await db.execute(select(Subject).where(Subject.subject_id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, f"Subject {subject_id} not found")
    return SubjectResponse.model_validate(subject)


@router.post("", response_model=SubjectResponse, status_code=201)
async def create_subject(
    req: SubjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new subject."""
    # Check if exists
    existing = await db.execute(select(Subject).where(Subject.subject_id == req.subject_id))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Subject {req.subject_id} already exists")

    subject = Subject(
        subject_id=req.subject_id,
        patient_ref=req.patient_ref,
        hospital_ids=req.hospital_ids,
        metadata_=req.metadata,
    )
    db.add(subject)
    await db.flush()
    return SubjectResponse.model_validate(subject)


@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    req: SubjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update subject information."""
    result = await db.execute(select(Subject).where(Subject.subject_id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, f"Subject {subject_id} not found")

    if req.patient_ref is not None:
        subject.patient_ref = req.patient_ref
    if req.hospital_ids is not None:
        subject.hospital_ids = req.hospital_ids
    if req.metadata is not None:
        subject.metadata_ = req.metadata

    await db.flush()
    return SubjectResponse.model_validate(subject)


@router.delete("/{subject_id}")
async def delete_subject(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a subject and all its data."""
    result = await db.execute(select(Subject).where(Subject.subject_id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(404, f"Subject {subject_id} not found")

    await db.delete(subject)
    await db.flush()
    return {"deleted": True, "subject_id": subject_id}
