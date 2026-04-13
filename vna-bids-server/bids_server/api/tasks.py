"""Tasks API - Async task management."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import Task
from bids_server.models.schemas import TaskCreate, TaskResponse
from bids_server.services.task_service import task_service

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status: queued, running, completed, failed, cancelled"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List tasks with pagination."""
    count_query = select(func.count()).select_from(Task)
    if status:
        count_query = count_query.where(Task.status == status)
    total = (await db.execute(count_query)).scalar() or 0

    tasks = await task_service.list_tasks(db, status=status, limit=limit, offset=offset)
    return {
        "items": [TaskResponse.model_validate(t) for t in tasks],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get task status and result."""
    task = await task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return TaskResponse.model_validate(task)


@router.post("", response_model=TaskResponse, status_code=202)
async def create_task(
    req: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a new async task.
    
    Supported actions:
    - convert: Convert between formats (e.g., DICOM to NIfTI)
    - analyze: Run analysis pipeline
    - export: Export data
    - validate: Validate BIDS structure
    - reindex: Reindex resources
    """
    task = await task_service.create_task(
        db,
        action=req.action,
        resource_ids=req.resource_ids,
        params=req.params,
        callback_url=req.callback_url,
    )
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a queued or running task."""
    cancelled = await task_service.cancel_task(db, task_id)
    if not cancelled:
        raise HTTPException(400, "Task cannot be cancelled (not found or already completed)")
    return {"cancelled": True, "task_id": task_id}
