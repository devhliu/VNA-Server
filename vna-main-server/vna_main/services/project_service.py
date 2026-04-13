"""Project management service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vna_main.models.database import Project, ProjectMember, ProjectResource


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_projects(
        self, *, offset: int = 0, limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(Project).options(selectinload(Project.members), selectinload(Project.resource_links))
        count_stmt = select(func.count()).select_from(Project)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.offset(offset).limit(limit).order_by(Project.created_at.desc())
        result = await self.session.execute(stmt)
        items = [self._serialize_project(p) for p in result.scalars().all()]
        return items, total

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        stmt = (
            select(Project)
            .where(Project.project_id == project_id)
            .options(selectinload(Project.members), selectinload(Project.resource_links))
        )
        result = await self.session.execute(stmt)
        project = result.scalar_one_or_none()
        if project is None:
            return None
        return self._serialize_project(project)

    async def create_project(self, data: dict[str, Any]) -> dict[str, Any]:
        project = Project(
            name=data["name"],
            description=data.get("description"),
            principal_investigator=data.get("principal_investigator"),
        )
        self.session.add(project)
        await self.session.flush()
        # Refresh to load relationships
        await self.session.refresh(project, ["members", "resource_links"])
        return self._serialize_project(project)

    async def update_project(self, project_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        project = await self.session.get(Project, project_id)
        if project is None:
            return None
        updatable_fields = {"name", "description", "principal_investigator", "is_active"}
        for key, value in data.items():
            if key in updatable_fields:
                setattr(project, key, value)
        await self.session.flush()
        await self.session.refresh(project, ["members", "resource_links"])
        return self._serialize_project(project)

    async def delete_project(self, project_id: str) -> bool:
        project = await self.session.get(Project, project_id)
        if project is None:
            return False
        await self.session.delete(project)
        await self.session.flush()
        return True

    async def add_member(
        self, project_id: str, patient_ref: str, role: str,
    ) -> ProjectMember | None:
        project = await self.session.get(Project, project_id)
        if project is None:
            return None
        member = ProjectMember(
            project_id=project_id,
            patient_ref=patient_ref,
            role=role,
        )
        self.session.add(member)
        await self.session.flush()
        return member

    async def list_members(
        self, project_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = (
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.joined_at)
        )
        count_stmt = select(func.count()).select_from(ProjectMember).where(
            ProjectMember.project_id == project_id
        )
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        items = [
            {"id": m.id, "patient_ref": m.patient_ref, "role": m.role,
             "joined_at": m.joined_at.isoformat() if m.joined_at else None}
            for m in result.scalars().all()
        ]
        return items, total

    async def add_resource(self, project_id: str, resource_id: str) -> ProjectResource | None:
        project = await self.session.get(Project, project_id)
        if project is None:
            return None
        link = ProjectResource(project_id=project_id, resource_id=resource_id)
        self.session.add(link)
        await self.session.flush()
        return link

    async def list_resources(
        self, project_id: str, *, offset: int = 0, limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(ProjectResource).where(ProjectResource.project_id == project_id)
        count_stmt = select(func.count()).select_from(
            select(ProjectResource).where(ProjectResource.project_id == project_id).subquery()
        )
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.offset(offset).limit(limit).order_by(ProjectResource.added_at)
        result = await self.session.execute(stmt)
        items = [
            {"id": r.id, "resource_id": r.resource_id,
             "added_at": r.added_at.isoformat() if r.added_at else None}
            for r in result.scalars().all()
        ]
        return items, total

    @staticmethod
    def _serialize_project(p: Project) -> dict[str, Any]:
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
