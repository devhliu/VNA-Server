"""Query API - Search resources (BIDSweb equivalent of QIDO-RS/C-FIND)."""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import Resource, Label
from bids_server.models.schemas import QueryRequest, QueryResponse, ResourceResponse

router = APIRouter(prefix="/api/query", tags=["Query"])


@router.post("", response_model=QueryResponse)
async def query_resources(
    req: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Query resources with flexible filters."""
    query = select(Resource)
    count_query = select(func.count(Resource.resource_id))
    conditions = []

    # Basic filters
    if req.subject_id:
        conditions.append(Resource.subject_id == req.subject_id)
    if req.session_id:
        conditions.append(Resource.session_id == req.session_id)
    if req.modality:
        conditions.append(Resource.modality.in_(req.modality))
    if req.source:
        conditions.append(Resource.source.in_(req.source))
    if req.file_type:
        conditions.append(Resource.file_type.in_(req.file_type))
    if req.dicom_ref:
        conditions.append(Resource.dicom_ref == req.dicom_ref)
    if req.content_hash:
        conditions.append(Resource.content_hash == req.content_hash)

    # Metadata filter using PostgreSQL JSONB operators
    if req.metadata:
        for key, value in req.metadata.items():
            # Proper JSONB containment check - works efficiently with GIN indexes
            conditions.append(Resource.metadata_.op('@>')({key: value}))

    # Time range
    if req.time_range:
        field = req.time_range.get("field", "created_at")
        time_col = Resource.created_at if field == "created_at" else Resource.updated_at
        if req.time_range.get("from"):
            conditions.append(time_col >= req.time_range["from"])
        if req.time_range.get("to"):
            conditions.append(time_col <= req.time_range["to"])

    # Label filters
    if req.labels:
        if req.labels.get("match"):
            for label_value in req.labels["match"]:
                subq = (
                    select(Label.resource_id)
                    .where(
                        or_(
                            Label.tag_key == label_value,
                            Label.tag_value == label_value,
                        )
                    )
                    .subquery()
                )
                conditions.append(Resource.resource_id.in_(select(subq)))

        if req.labels.get("any"):
            any_conditions = []
            for label_value in req.labels["any"]:
                any_conditions.append(Label.tag_key == label_value)
                any_conditions.append(Label.tag_value == label_value)
            subq = (
                select(Label.resource_id)
                .where(or_(*any_conditions))
                .distinct()
                .subquery()
            )
            conditions.append(Resource.resource_id.in_(select(subq)))

        if req.labels.get("exclude"):
            for label_value in req.labels["exclude"]:
                subq = (
                    select(Label.resource_id)
                    .where(
                        or_(
                            Label.tag_key == label_value,
                            Label.tag_value == label_value,
                        )
                    )
                    .subquery()
                )
                conditions.append(~Resource.resource_id.in_(select(subq)))

    # Full-text search (handled by search_service, simplified here)
    if req.search:
        pattern = f"%{req.search}%"
        conditions.append(
            or_(
                Resource.file_name.like(pattern),
                Resource.modality.like(pattern),
                Resource.bids_path.like(pattern),
            )
        )

    # Apply conditions
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    # Sort
    if req.sort:
        for s in req.sort:
            col = getattr(Resource, s.get("field", "created_at"), Resource.created_at)
            if s.get("order", "asc") == "desc":
                query = query.order_by(col.desc())
            else:
                query = query.order_by(col.asc())
    else:
        query = query.order_by(Resource.created_at.desc())

    # Count
    total = (await db.execute(count_query)).scalar() or 0

    # Pagination
    query = query.limit(req.limit).offset(req.offset)
    result = await db.execute(query)
    resources = result.scalars().all()

    return QueryResponse(
        total=total,
        resources=[ResourceResponse.model_validate(r) for r in resources],
    )
