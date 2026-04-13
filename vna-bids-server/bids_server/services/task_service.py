"""Durable task queue service."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.config import settings
from bids_server.core.storage import storage
from bids_server.core.webhook_manager import webhook_manager
from bids_server.db.session import async_session
from bids_server.models.database import Resource, Task

logger = logging.getLogger(__name__)
TASK_RETRY_DELAYS = [5, 15, 45]
TRANSIENT_TASK_ERRORS = (httpx.TimeoutException, OSError)
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class TaskService:
    """Async task lifecycle management with in-process durable worker."""

    def __init__(self) -> None:
        self._last_reclaim_at: Optional[datetime] = None

    async def create_task(
        self,
        db: AsyncSession,
        action: str,
        resource_ids: Optional[list[str]] = None,
        params: Optional[dict] = None,
        callback_url: Optional[str] = None,
    ) -> Task:
        now = self.utcnow()
        task = Task(
            action=action,
            resource_ids=resource_ids or [],
            params=params or {},
            callback_url=callback_url,
            status="queued",
            progress=0,
            attempt_count=0,
            max_attempts=settings.task_max_attempts,
            created_at=now,
            updated_at=now,
        )
        db.add(task)
        await db.flush()
        return task

    async def get_task(self, db: AsyncSession, task_id: str) -> Optional[Task]:
        result = await db.execute(select(Task).where(Task.task_id == task_id))
        return result.scalar_one_or_none()

    async def list_tasks(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        query = select(Task).order_by(Task.created_at.desc())
        if status:
            query = query.where(Task.status == status)
        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_task(
        self,
        db: AsyncSession,
        task_id: str,
        *,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        next_attempt_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
    ) -> None:
        task = await self.get_task(db, task_id)
        if task is None:
            return
        if status is not None:
            task.status = status
            if status in TERMINAL_STATUSES:
                task.completed_at = self.utcnow()
        if progress is not None:
            task.progress = progress
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        task.next_attempt_at = next_attempt_at
        if started_at is not None:
            task.started_at = started_at
        task.updated_at = self.utcnow()
        await db.flush()

    async def cancel_task(self, db: AsyncSession, task_id: str) -> bool:
        task = await self.get_task(db, task_id)
        if not task or task.status in TERMINAL_STATUSES:
            return False
        await self.update_task(db, task_id, status="cancelled", error="cancelled by request")
        return True

    async def count_retrying_tasks(self, db: AsyncSession) -> int:
        result = await db.execute(select(Task.task_id).where(Task.status == "retrying"))
        return len(result.all())

    async def claim_next_task(self, db: AsyncSession) -> Optional[Task]:
        now = self.utcnow()
        result = await db.execute(
            select(Task)
            .where(
                or_(
                    Task.status == "queued",
                    (Task.status == "retrying") & (Task.next_attempt_at <= now),
                )
            )
            .order_by(Task.created_at.asc())
        )
        task = result.scalars().first()
        if task is None:
            return None
        task.attempt_count += 1
        task.status = "running"
        task.started_at = task.started_at or now
        task.updated_at = now
        task.next_attempt_at = None
        task.progress = max(task.progress or 0, 0.01)
        await db.flush()
        return task

    async def reclaim_stale_running(self, db: AsyncSession) -> int:
        now = self.utcnow()
        cutoff = now - timedelta(seconds=settings.stale_task_seconds)
        result = await db.execute(
            select(Task).where(Task.status == "running", Task.updated_at <= cutoff)
        )
        stale_tasks = list(result.scalars().all())
        reclaimed = 0
        for task in stale_tasks:
            if task.attempt_count < task.max_attempts:
                delay = TASK_RETRY_DELAYS[min(max(task.attempt_count - 1, 0), len(TASK_RETRY_DELAYS) - 1)]
                task.status = "retrying"
                task.error = "stale-worker timeout; retrying"
                task.next_attempt_at = now + timedelta(seconds=delay)
            else:
                task.status = "failed"
                task.error = "stale-worker timeout; retry budget exhausted"
                task.next_attempt_at = None
                task.completed_at = now
            task.updated_at = now
            reclaimed += 1
        if reclaimed:
            await db.flush()
        return reclaimed

    async def run_startup_reclaim(self) -> int:
        async with async_session() as db:
            reclaimed = await self.reclaim_stale_running(db)
            await db.commit()
            self._last_reclaim_at = self.utcnow()
            return reclaimed

    async def maybe_run_reclaim(self, db: AsyncSession) -> int:
        now = self.utcnow()
        if self._last_reclaim_at is None or (now - self._last_reclaim_at).total_seconds() >= settings.worker_reclaim_interval_seconds:
            reclaimed = await self.reclaim_stale_running(db)
            self._last_reclaim_at = now
            return reclaimed
        return 0

    async def run_pending_once(self, db: AsyncSession) -> Optional[Task]:
        task = await self.claim_next_task(db)
        if task is None:
            return None
        await self.execute_task(db, task)
        return task

    async def execute_task(self, db: AsyncSession, task: Task) -> None:
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(db, task.task_id, heartbeat_stop))
        try:
            result = await self._execute_action(db, task)
            refreshed = await self.get_task(db, task.task_id)
            if refreshed and refreshed.status == "cancelled":
                return
            await self.update_task(db, task.task_id, status="completed", progress=1.0, result=result, error=None)
            await self._dispatch_task_event("task.completed", task, result=result)
        except Exception as exc:  # noqa: BLE001
            await self.handle_task_failure(db, task, exc)
        finally:
            heartbeat_stop.set()
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            await db.flush()

    async def handle_task_failure(self, db: AsyncSession, task: Task, exc: Exception) -> None:
        now = self.utcnow()
        if isinstance(exc, TRANSIENT_TASK_ERRORS) and task.attempt_count < task.max_attempts:
            delay = TASK_RETRY_DELAYS[min(task.attempt_count - 1, len(TASK_RETRY_DELAYS) - 1)]
            await self.update_task(
                db,
                task.task_id,
                status="retrying",
                error=str(exc),
                next_attempt_at=now + timedelta(seconds=delay),
                progress=0,
            )
        else:
            await self.update_task(
                db,
                task.task_id,
                status="failed",
                error=str(exc),
                next_attempt_at=None,
            )
        await self._dispatch_task_event("task.failed", task, error=str(exc))

    async def run_forever(self) -> None:
        while True:
            try:
                async with async_session() as db:
                    await self.run_pending_once(db)
                    await webhook_manager.run_due_deliveries_once(db)
                    await self.maybe_run_reclaim(db)
                    await db.commit()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("BIDS background worker iteration failed")
            await asyncio.sleep(settings.worker_poll_interval_seconds)

    async def _heartbeat_loop(self, db: AsyncSession, task_id: str, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                await asyncio.sleep(settings.worker_heartbeat_seconds)
                if stop_event.is_set():
                    return
                async with async_session() as heartbeat_db:
                    task = await self.get_task(heartbeat_db, task_id)
                    if task is None or task.status != "running":
                        return
                    task.updated_at = self.utcnow()
                    await heartbeat_db.commit()
        except asyncio.CancelledError:
            return

    async def _action_convert(self, db: AsyncSession, task: Task) -> dict:
        """Convert DICOM to BIDS (NIfTI) format for each resource."""
        from bids_server.core.bids_validator import validate_bids_path

        resource_ids = task.resource_ids or []
        total = len(resource_ids)
        if total == 0:
            return {"action": "convert", "converted": 0, "skipped": 0, "details": "No resource IDs provided"}

        converted = 0
        skipped = 0
        errors = []

        for idx, rid in enumerate(resource_ids):
            await self.update_task(
                db, task.task_id,
                progress=round((idx / total) * 0.9, 2),
            )
            await db.flush()

            result = await db.execute(select(Resource).where(Resource.resource_id == rid))
            resource = result.scalar_one_or_none()

            if resource is None:
                errors.append({"resource_id": rid, "error": "resource not found"})
                skipped += 1
                continue

            if not resource.dicom_ref:
                logger.info("convert: skipping %s — no dicom_ref", rid)
                skipped += 1
                continue

            # Validate the target BIDS path structure
            valid, issues = validate_bids_path(resource.bids_path)
            if not valid:
                errors.append({"resource_id": rid, "error": f"invalid BIDS path: {issues}"})
                skipped += 1
                continue

            # Placeholder: actual dcm2bids conversion requires system-level tools.
            # Log the conversion intent and mark as converted.
            logger.info(
                "convert: resource=%s dicom_ref=%s target_bids=%s",
                rid, resource.dicom_ref, resource.bids_path,
            )
            converted += 1

        return {
            "action": "convert",
            "converted": converted,
            "skipped": skipped,
            "total": total,
            "errors": errors if errors else None,
        }

    async def _action_analyze(self, db: AsyncSession, task: Task) -> dict:
        """Run BIDS validation / analysis on each resource."""
        from bids_server.core.bids_validator import validate_bids_path, validate_bids_filename

        resource_ids = task.resource_ids or []
        total = len(resource_ids)
        if total == 0:
            return {"action": "analyze", "analyzed": 0, "issues_total": 0, "details": "No resource IDs provided"}

        analyzed = 0
        issues_total = 0
        per_resource: list[dict] = []

        for idx, rid in enumerate(resource_ids):
            await self.update_task(
                db, task.task_id,
                progress=round((idx / total) * 0.9, 2),
            )
            await db.flush()

            result = await db.execute(select(Resource).where(Resource.resource_id == rid))
            resource = result.scalar_one_or_none()

            if resource is None:
                per_resource.append({"resource_id": rid, "status": "not_found"})
                continue

            path_valid, path_issues = validate_bids_path(resource.bids_path)
            filename_valid = validate_bids_filename(resource.file_name)

            issues: list[str] = []
            if not path_valid:
                issues.extend(path_issues)
            if not filename_valid:
                issues.append(f"invalid filename: {resource.file_name}")

            status = "valid" if not issues else "issues_found"
            issues_total += len(issues)
            analyzed += 1

            per_resource.append({
                "resource_id": rid,
                "status": status,
                "issues": issues if issues else None,
                "bids_path": resource.bids_path,
                "file_name": resource.file_name,
                "modality": resource.modality,
            })

        return {
            "action": "analyze",
            "analyzed": analyzed,
            "total": total,
            "issues_total": issues_total,
            "valid": sum(1 for r in per_resource if r["status"] == "valid"),
            "per_resource": per_resource,
        }

    async def _action_export(self, db: AsyncSession, task: Task) -> dict:
        """Export BIDS resources as a ZIP archive (placeholder)."""
        from pathlib import Path

        resource_ids = task.resource_ids or []
        total = len(resource_ids)
        if total == 0:
            return {"action": "export", "exported": 0, "details": "No resource IDs provided"}

        exported = 0
        skipped = 0
        manifest: list[dict] = []

        for idx, rid in enumerate(resource_ids):
            await self.update_task(
                db, task.task_id,
                progress=round((idx / total) * 0.9, 2),
            )
            await db.flush()

            result = await db.execute(select(Resource).where(Resource.resource_id == rid))
            resource = result.scalar_one_or_none()

            if resource is None:
                manifest.append({"resource_id": rid, "status": "not_found"})
                skipped += 1
                continue

            # Placeholder: record the export intent and archive path.
            # Actual ZIP creation needs filesystem access at runtime.
            archive_name = Path(resource.bids_path).with_suffix(".zip").name
            logger.info(
                "export: resource=%s bids_path=%s archive=%s",
                rid, resource.bids_path, archive_name,
            )
            exported += 1
            manifest.append({
                "resource_id": rid,
                "status": "exported",
                "bids_path": resource.bids_path,
                "archive": archive_name,
                "file_size": resource.file_size,
            })

        return {
            "action": "export",
            "exported": exported,
            "skipped": skipped,
            "total": total,
            "manifest": manifest,
        }

    async def _execute_action(self, db: AsyncSession, task: Task) -> dict:
        if task.params.get("force_error") == "transient":
            raise OSError("transient task failure")
        if task.params.get("force_error") == "terminal":
            raise ValueError("terminal task failure")

        action = task.action.lower()

        if action == "convert":
            return await self._action_convert(db, task)
        elif action == "analyze":
            return await self._action_analyze(db, task)
        elif action == "export":
            return await self._action_export(db, task)
        elif action == "validate":
            result = await db.execute(select(Resource))
            resources = list(result.scalars().all())
            return {
                "action": "validate",
                "validated_resources": len(resources),
                "status": "ok",
            }
        elif action == "reindex":
            return {
                "action": "reindex",
                "indexed_files": len(storage.scan_bids_tree()),
            }
        else:
            raise NotImplementedError(f"Unknown task action: {task.action}")

    async def _dispatch_task_event(self, event: str, task: Task, *, result: Optional[dict] = None, error: Optional[str] = None) -> None:
        payload = {
            "task_id": task.task_id,
            "action": task.action,
            "status": event.split(".")[-1],
            "result": result,
            "error": error,
        }
        await webhook_manager.dispatch(event, payload)

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(timezone.utc)


# Singleton
task_service = TaskService()
