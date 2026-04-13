"""Project management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.project_service import ProjectService
from vna_common.responses import PaginatedResponse
from vna_main.services.audit_service import AuditService

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    principal_investigator: str | None = None


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    principal_investigator: str | None = None
    is_active: bool | None = None


class MemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_ref: str
    role: str = "member"


class ResourceLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_id: str


def _serialize(p) -> dict[str, Any]:
    if isinstance(p, dict):
        return p
    return {
        "project_id": p.project_id,
        "name": p.name,
        "description": p.description,
        "principal_investigator": p.principal_investigator,
        "is_active": p.is_active,
        "member_count": len(p.members) if p.members else 0,
        "resource_count": len(p.resource_links) if p.resource_links else 0,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("", response_model=PaginatedResponse[dict])
async def list_projects(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    svc = ProjectService(session)
    items, total = await svc.list_projects(offset=offset, limit=limit)
    return PaginatedResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit
    )


@router.post("", status_code=201)
async def create_project(
    body: ProjectCreate,
    session: AsyncSession = Depends(get_session),
):
    svc = ProjectService(session)
    audit_svc = AuditService(session)
    project = await svc.create_project(body.model_dump(exclude_none=True))
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="create",
        resource_type="project",
        resource_id=project["project_id"],
        details={"name": project["name"], "principal_investigator": project.get("principal_investigator")}
    )
    
    return project  # Already a dict from service


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    svc = ProjectService(session)
    project = await svc.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
):
    svc = ProjectService(session)
    audit_svc = AuditService(session)
    project = await svc.update_project(project_id, body.model_dump(exclude_none=True))
    if project is None:
        raise HTTPException(404, "Project not found")
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="update",
        resource_type="project",
        resource_id=project_id,
        details={"updated_fields": list(body.model_dump(exclude_none=True).keys())}
    )
    
    return project  # Already a dict from service


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
):
    svc = ProjectService(session)
    audit_svc = AuditService(session)
    
    # Get project info before deletion for audit
    project = await svc.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    
    ok = await svc.delete_project(project_id)
    if not ok:
        raise HTTPException(404, "Project not found")
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="delete",
        resource_type="project",
        resource_id=project_id,
        details={"name": project["name"]}
    )


# --- Members ---

@router.get("/{project_id}/members", response_model=PaginatedResponse[dict])
async def list_members(
    project_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    svc = ProjectService(session)
    project = await svc.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    items, total = await svc.list_members(project_id, offset=offset, limit=limit)
    return PaginatedResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit
    )


@router.post("/{project_id}/members", status_code=201)
async def add_member(
    project_id: str,
    body: MemberCreate,
    session: AsyncSession = Depends(get_session),
):
    svc = ProjectService(session)
    audit_svc = AuditService(session)
    member = await svc.add_member(project_id, body.patient_ref, body.role)
    if member is None:
        raise HTTPException(404, "Project not found")
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="create",
        resource_type="project_member",
        resource_id=str(member.id),
        details={"project_id": project_id, "patient_ref": body.patient_ref, "role": body.role}
    )
    
    return {
        "id": member.id,
        "patient_ref": member.patient_ref,
        "role": member.role,
        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
    }


# --- Resources ---

@router.get("/{project_id}/resources", response_model=PaginatedResponse[dict])
async def list_resources(
    project_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    svc = ProjectService(session)
    project = await svc.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    items, total = await svc.list_resources(project_id, offset=offset, limit=limit)
    return PaginatedResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit
    )


@router.post("/{project_id}/resources", status_code=201)
async def add_resource(
    project_id: str,
    body: ResourceLinkCreate,
    session: AsyncSession = Depends(get_session),
):
    svc = ProjectService(session)
    audit_svc = AuditService(session)
    link = await svc.add_resource(project_id, body.resource_id)
    if link is None:
        raise HTTPException(404, "Project not found")
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="create",
        resource_type="project_resource",
        resource_id=str(link.id),
        details={"project_id": project_id, "resource_id": body.resource_id}
    )
    
    return {
        "id": link.id,
        "resource_id": link.resource_id,
        "added_at": link.added_at.isoformat() if link.added_at else None,
    }
