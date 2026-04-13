"""Sessions API - Scan session management."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import Session
from bids_server.models.schemas import SessionCreate, SessionUpdate, SessionResponse

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


@router.get("")
async def list_sessions(
    subject_id: Optional[str] = Query(None, description="Filter by subject"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List sessions, optionally filtered by subject."""
    query = select(Session).order_by(Session.session_id)
    count_query = select(func.count()).select_from(Session)
    
    if subject_id:
        query = query.where(Session.subject_id == subject_id)
        count_query = count_query.where(Session.subject_id == subject_id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    items = [SessionResponse.model_validate(s) for s in result.scalars().all()]
    
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get session details."""
    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")
    return SessionResponse.model_validate(session)


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    req: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new session."""
    existing = await db.execute(select(Session).where(Session.session_id == req.session_id))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Session {req.session_id} already exists")

    session = Session(
        session_id=req.session_id,
        subject_id=req.subject_id,
        session_label=req.session_label,
        scan_date=req.scan_date,
        metadata_=req.metadata,
    )
    db.add(session)
    await db.flush()
    return SessionResponse.model_validate(session)


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    req: SessionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update session information."""
    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")

    if req.session_label is not None:
        session.session_label = req.session_label
    if req.scan_date is not None:
        session.scan_date = req.scan_date
    if req.metadata is not None:
        session.metadata_ = req.metadata

    await db.flush()
    return SessionResponse.model_validate(session)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a session and all its resources."""
    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")

    await db.delete(session)
    await db.flush()
    return {"deleted": True, "session_id": session_id}
