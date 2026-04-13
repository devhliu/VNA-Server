"""Replication service for multi-datacenter support."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.config import settings
from bids_server.models.database import (
    Resource,
    Subject,
    Session as BidsSession,
    Label,
    Annotation,
)

logger = logging.getLogger(__name__)


class ReplicationService:
    """Service for replicating data across datacenters."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._client = httpx.AsyncClient(timeout=30.0)
        self._local_dc = settings.get_datacenter_config()
    
    async def close(self):
        await self._client.aclose()
    
    async def get_sync_status(self) -> dict[str, Any]:
        """Get the current sync status for all datacenters."""
        endpoints = settings.get_replication_endpoints()
        if not endpoints:
            return {
                "enabled": False,
                "local_datacenter": self._local_dc.id,
                "remote_datacenters": [],
            }
        
        status = {
            "enabled": settings.replication_enabled,
            "local_datacenter": self._local_dc.id,
            "remote_datacenters": [],
        }
        
        for endpoint in endpoints:
            try:
                resp = await self._client.get(f"{endpoint}/health")
                dc_status = {
                    "endpoint": endpoint,
                    "healthy": resp.status_code == 200,
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }
            except Exception as e:
                logger.warning("Health check failed for %s: %s", endpoint, e)
                dc_status = {
                    "endpoint": endpoint,
                    "healthy": False,
                    "error": str(e),
                    "last_check": datetime.now(timezone.utc).isoformat(),
                }
            status["remote_datacenters"].append(dc_status)

        return status
    
    async def push_changes(
        self,
        resource_type: str,
        resource_id: str,
        action: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Push changes to all remote datacenters."""
        if not settings.replication_enabled:
            return {"pushed": False, "reason": "replication_disabled"}
        
        endpoints = settings.get_replication_endpoints()
        if not endpoints:
            return {"pushed": False, "reason": "no_endpoints"}
        
        payload = {
            "source_datacenter": self._local_dc.id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        results = []
        for endpoint in endpoints:
            try:
                resp = await self._client.post(
                    f"{endpoint}/api/replication/receive",
                    json=payload,
                )
                results.append({
                    "endpoint": endpoint,
                    "success": resp.status_code == 200,
                    "status_code": resp.status_code,
                })
            except Exception as e:
                logger.warning("Push to %s failed: %s", endpoint, e)
                results.append({
                    "endpoint": endpoint,
                    "success": False,
                    "error": str(e),
                })
        
        return {
            "pushed": True,
            "results": results,
        }
    
    async def receive_changes(
        self,
        source_datacenter: str,
        resource_type: str,
        resource_id: str,
        action: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Receive and apply changes from a remote datacenter."""
        if source_datacenter == self._local_dc.id:
            return {"applied": False, "reason": "self_replication_ignored"}
        
        try:
            if resource_type == "resource":
                result = await self._apply_resource_change(action, data)
            elif resource_type == "subject":
                result = await self._apply_subject_change(action, data)
            elif resource_type == "session":
                result = await self._apply_session_change(action, data)
            elif resource_type == "label":
                result = await self._apply_label_change(action, data)
            elif resource_type == "annotation":
                result = await self._apply_annotation_change(action, data)
            else:
                return {"applied": False, "reason": f"unknown_type: {resource_type}"}
            
            await self.session.commit()
            return {"applied": True, "result": result}
        except Exception as e:
            logger.error("Receive changes failed from %s: %s", source_datacenter, e, exc_info=True)
            await self.session.rollback()
            return {"applied": False, "error": str(e)}
    
    async def _apply_resource_change(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        if action == "create":
            resource = Resource(
                resource_id=data.get("resource_id"),
                subject_id=data.get("subject_id"),
                session_id=data.get("session_id"),
                modality=data.get("modality", "unknown"),
                bids_path=data["bids_path"],
                file_name=data.get("file_name"),
                file_type=data.get("file_type"),
                file_size=data.get("file_size", 0),
                content_hash=data.get("content_hash"),
                source=data.get("source", "replication"),
                metadata_=data.get("metadata"),
            )
            self.session.add(resource)
            await self.session.flush()
            return {"resource_id": resource.resource_id}
        
        elif action == "update":
            stmt = select(Resource).where(Resource.bids_path == data["bids_path"])
            result = await self.session.execute(stmt)
            resource = result.scalar_one_or_none()
            if resource:
                for key, value in data.items():
                    if key == "metadata":
                        key = "metadata_"
                    if hasattr(resource, key) and key not in ("resource_id", "created_at"):
                        setattr(resource, key, value)
                return {"resource_id": resource.resource_id}
            return {"error": "resource_not_found"}
        
        elif action == "delete":
            stmt = select(Resource).where(Resource.bids_path == data["bids_path"])
            result = await self.session.execute(stmt)
            resource = result.scalar_one_or_none()
            if resource:
                await self.session.delete(resource)
                return {"deleted": True}
            return {"error": "resource_not_found"}
        
        return {"error": f"unknown_action: {action}"}
    
    async def _apply_subject_change(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        if action == "create":
            subject = Subject(
                subject_id=data["subject_id"],
                patient_ref=data.get("patient_ref"),
                hospital_ids=data.get("hospital_ids"),
                metadata_=data.get("metadata"),
            )
            self.session.add(subject)
            return {"subject_id": subject.subject_id}
        
        elif action == "update":
            stmt = select(Subject).where(Subject.subject_id == data["subject_id"])
            result = await self.session.execute(stmt)
            subject = result.scalar_one_or_none()
            if subject:
                for key, value in data.items():
                    if key == "metadata":
                        key = "metadata_"
                    if hasattr(subject, key) and key != "subject_id":
                        setattr(subject, key, value)
                return {"subject_id": subject.subject_id}
            return {"error": "subject_not_found"}
        
        elif action == "delete":
            stmt = select(Subject).where(Subject.subject_id == data["subject_id"])
            result = await self.session.execute(stmt)
            subject = result.scalar_one_or_none()
            if subject:
                await self.session.delete(subject)
                return {"deleted": True}
            return {"error": "subject_not_found"}
        
        return {"error": f"unknown_action: {action}"}
    
    async def _apply_session_change(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        if action == "create":
            session = BidsSession(
                session_id=data["session_id"],
                subject_id=data.get("subject_id"),
                session_label=data.get("session_label"),
                scan_date=data.get("scan_date"),
                metadata_=data.get("metadata"),
            )
            self.session.add(session)
            return {"session_id": session.session_id}
        
        elif action in ("update", "delete"):
            stmt = select(BidsSession).where(BidsSession.session_id == data["session_id"])
            result = await self.session.execute(stmt)
            session = result.scalar_one_or_none()
            if session:
                if action == "delete":
                    await self.session.delete(session)
                    return {"deleted": True}
                else:
                    for key, value in data.items():
                        if key == "metadata":
                            key = "metadata_"
                        if hasattr(session, key) and key != "session_id":
                            setattr(session, key, value)
                    return {"session_id": session.session_id}
            return {"error": "session_not_found"}
        
        return {"error": f"unknown_action: {action}"}
    
    async def _apply_label_change(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        if action == "create":
            label = Label(
                resource_id=data.get("resource_id"),
                level=data.get("level", "file"),
                target_path=data.get("target_path"),
                tag_key=data["tag_key"],
                tag_value=data["tag_value"],
                tagged_by=data.get("tagged_by"),
            )
            self.session.add(label)
            await self.session.flush()
            return {"label_id": label.id}
        
        elif action == "delete":
            stmt = select(Label).where(Label.id == data["id"])
            result = await self.session.execute(stmt)
            label = result.scalar_one_or_none()
            if label:
                await self.session.delete(label)
                return {"deleted": True}
            return {"error": "label_not_found"}
        
        return {"error": f"unknown_action: {action}"}
    
    async def _apply_annotation_change(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        if action == "create":
            annotation = Annotation(
                resource_id=data.get("resource_id"),
                annotation_type=data["annotation_type"],
                content=data.get("content"),
            )
            self.session.add(annotation)
            await self.session.flush()
            return {"annotation_id": annotation.id}
        
        elif action in ("update", "delete"):
            stmt = select(Annotation).where(Annotation.id == data["id"])
            result = await self.session.execute(stmt)
            annotation = result.scalar_one_or_none()
            if annotation:
                if action == "delete":
                    await self.session.delete(annotation)
                    return {"deleted": True}
                else:
                    for key, value in data.items():
                        if hasattr(annotation, key) and key != "id":
                            setattr(annotation, key, value)
                    return {"annotation_id": annotation.id}
            return {"error": "annotation_not_found"}
        
        return {"error": f"unknown_action: {action}"}
    
    async def get_pending_sync_items(
        self,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get items that need to be synced to remote datacenters."""
        items = []
        
        resources_stmt = select(Resource)
        if since:
            resources_stmt = resources_stmt.where(Resource.updated_at > since)
        resources_stmt = resources_stmt.limit(limit)
        
        resources_result = await self.session.execute(resources_stmt)
        for r in resources_result.scalars().all():
            items.append({
                "resource_type": "resource",
                "resource_id": r.resource_id,
                "action": "update",
                "data": {
                    "resource_id": r.resource_id,
                    "subject_id": r.subject_id,
                    "session_id": r.session_id,
                    "modality": r.modality,
                    "bids_path": r.bids_path,
                    "file_name": r.file_name,
                    "file_type": r.file_type,
                    "file_size": r.file_size,
                    "content_hash": r.content_hash,
                    "source": r.source,
                    "metadata": r.metadata_,
                },
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            })
        
        return items


async def run_replication_sync(session: AsyncSession):
    """Background task to sync data to remote datacenters."""
    if not settings.replication_enabled:
        return
    
    service = ReplicationService(session)
    try:
        items = await service.get_pending_sync_items(limit=settings.replication_batch_size)
        
        for item in items:
            await service.push_changes(
                resource_type=item["resource_type"],
                resource_id=item["resource_id"],
                action=item["action"],
                data=item["data"],
            )
    finally:
        await service.close()
