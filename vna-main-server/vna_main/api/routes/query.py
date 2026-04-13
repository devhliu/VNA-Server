"""Unified query API route - query across DICOM + BIDS."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vna_main.models.database import ResourceIndex, PatientMapping, Label, get_session
from vna_main.services.audit_service import AuditService

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Patient filters
    patient_ref: str | None = None
    hospital_id: str | None = None
    # Source filters
    source_type: str | None = None
    data_type: str | None = None
    # DICOM filters
    dicom_study_uid: str | None = None
    dicom_series_uid: str | None = None
    # BIDS filters
    bids_subject_id: str | None = None
    bids_session_id: str | None = None
    # Label filters (AND logic: resource must have all listed labels)
    labels: list[dict[str, str]] | None = None  # [{"tag_key": "...", "tag_value": "..."}, ...]
    # Free text search across file_name, content_hash, metadata
    text_search: str | None = None
    # Pagination
    offset: int = 0
    limit: int = 50


def _serialize_resource(r) -> dict:
    return {
        "resource_id": r.resource_id,
        "patient_ref": r.patient_ref,
        "source_type": r.source_type,
        "dicom_study_uid": r.dicom_study_uid,
        "dicom_series_uid": r.dicom_series_uid,
        "dicom_sop_uid": r.dicom_sop_uid,
        "bids_subject_id": r.bids_subject_id,
        "bids_session_id": r.bids_session_id,
        "bids_path": r.bids_path,
        "data_type": r.data_type,
        "file_name": r.file_name,
        "file_size": r.file_size,
        "content_hash": r.content_hash,
        "metadata": r.metadata_,
        "labels": [
            {"tag_key": l.tag_key, "tag_value": l.tag_value, "tag_type": l.tag_type}
            for l in (r.labels or [])
        ],
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.post("")
async def unified_query(
    body: QueryRequest,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(ResourceIndex).options(selectinload(ResourceIndex.labels))
    count_stmt = select(ResourceIndex.resource_id)

    # Join patient if hospital_id filter
    if body.hospital_id:
        stmt = stmt.join(PatientMapping, ResourceIndex.patient_ref == PatientMapping.patient_ref)
        stmt = stmt.where(PatientMapping.hospital_id == body.hospital_id)
        count_stmt = count_stmt.join(PatientMapping, ResourceIndex.patient_ref == PatientMapping.patient_ref)
        count_stmt = count_stmt.where(PatientMapping.hospital_id == body.hospital_id)

    # Simple filters
    filters = []
    if body.patient_ref:
        filters.append(ResourceIndex.patient_ref == body.patient_ref)
    if body.source_type:
        filters.append(ResourceIndex.source_type == body.source_type)
    if body.data_type:
        filters.append(ResourceIndex.data_type == body.data_type)
    if body.dicom_study_uid:
        filters.append(ResourceIndex.dicom_study_uid == body.dicom_study_uid)
    if body.dicom_series_uid:
        filters.append(ResourceIndex.dicom_series_uid == body.dicom_series_uid)
    if body.bids_subject_id:
        filters.append(ResourceIndex.bids_subject_id == body.bids_subject_id)
    if body.bids_session_id:
        filters.append(ResourceIndex.bids_session_id == body.bids_session_id)

    # Text search
    if body.text_search:
        pattern = f"%{body.text_search}%"
        filters.append(
            or_(
                ResourceIndex.file_name.ilike(pattern),
                ResourceIndex.content_hash.ilike(pattern),
            )
        )

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    # Label filters - each label is an AND condition
    if body.labels:
        for lbl_filter in body.labels:
            subq = (
                select(Label.resource_id)
                .where(
                    Label.tag_key == lbl_filter["tag_key"],
                    Label.tag_value == lbl_filter["tag_value"],
                )
                .scalar_subquery()
            )
            stmt = stmt.where(ResourceIndex.resource_id.in_(subq))
            count_stmt = count_stmt.where(ResourceIndex.resource_id.in_(subq))

    # Count
    from sqlalchemy import func
    total = (await session.execute(select(func.count()).select_from(count_stmt.subquery()))).scalar() or 0

    # Results
    stmt = stmt.offset(body.offset).limit(body.limit).order_by(ResourceIndex.created_at.desc())
    result = await session.execute(stmt)
    resources = list(result.scalars().unique().all())
    
    # Audit log for query operations
    audit_svc = AuditService(session)
    await audit_svc.log(
        action="query",
        resource_type="query",
        resource_id="unified_query",
        details={
            "filters_applied": body.model_dump(exclude_none=True),
            "result_count": len(resources)
        }
    )

    return {
        "total": total,
        "items": [_serialize_resource(r) for r in resources],
        "query": body.model_dump(exclude_none=True),
    }
