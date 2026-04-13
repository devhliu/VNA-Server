"""Label CRUD service with full-text search and history tracking."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from vna_main.models.database import Label, LabelHistory

logger = logging.getLogger(__name__)


class LabelService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_labels(
        self,
        *,
        tag_type: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        """List all unique tag_key/tag_value pairs with counts."""
        # Use subquery for distinct count (SQLite compatible)
        subq = select(Label.tag_key, Label.tag_value, Label.tag_type)
        if tag_type:
            subq = subq.where(Label.tag_type == tag_type)
        if search:
            pattern = f"%{search}%"
            subq = subq.where(
                or_(Label.tag_key.ilike(pattern), Label.tag_value.ilike(pattern))
            )
        subq = subq.distinct().subquery()
        count_stmt = select(func.count()).select_from(subq)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(
            Label.tag_key,
            Label.tag_value,
            Label.tag_type,
            func.count(Label.id).label("count"),
        ).group_by(Label.tag_key, Label.tag_value, Label.tag_type)

        if tag_type:
            stmt = stmt.where(Label.tag_type == tag_type)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(Label.tag_key.ilike(pattern), Label.tag_value.ilike(pattern))
            )

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        items = [
            {"tag_key": row.tag_key, "tag_value": row.tag_value, "tag_type": row.tag_type, "count": row.count}
            for row in result.all()
        ]
        return items, total

    async def get_resource_labels(self, resource_id: str) -> list[Label]:
        stmt = select(Label).where(Label.resource_id == resource_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def set_labels(
        self,
        resource_id: str,
        labels: list[dict[str, Any]],
        *,
        tagged_by: str | None = None,
    ) -> list[Label]:
        existing = await self.get_resource_labels(resource_id)
        for lbl in existing:
            hist = LabelHistory(
                resource_id=resource_id,
                tag_key=lbl.tag_key,
                tag_value=lbl.tag_value,
                tag_type=lbl.tag_type,
                action="deleted",
                tagged_by=lbl.tagged_by,
                tagged_at=lbl.tagged_at,
            )
            self.session.add(hist)
            await self.session.delete(lbl)
        await self.session.flush()

        created = []
        for item in labels:
            label = Label(
                resource_id=resource_id,
                tag_key=item["tag_key"],
                tag_value=item["tag_value"],
                tag_type=item.get("tag_type", "custom"),
                tagged_by=tagged_by or item.get("tagged_by"),
                tagged_at=datetime.now(timezone.utc),
            )
            self.session.add(label)
            hist = LabelHistory(
                resource_id=resource_id,
                tag_key=item["tag_key"],
                tag_value=item["tag_value"],
                tag_type=item.get("tag_type", "custom"),
                action="created",
                tagged_by=tagged_by or item.get("tagged_by"),
                tagged_at=label.tagged_at,
            )
            self.session.add(hist)
            created.append(label)
        await self.session.flush()
        return created

    async def patch_labels(
        self,
        resource_id: str,
        labels: list[dict[str, Any]],
        *,
        tagged_by: str | None = None,
    ) -> list[Label]:
        """Add or update labels without removing existing ones."""
        existing_stmt = select(Label).where(Label.resource_id == resource_id)
        result = await self.session.execute(existing_stmt)
        existing_map = {(lbl.tag_key, lbl.tag_value): lbl for lbl in result.scalars().all()}

        created = []
        for item in labels:
            key = (item["tag_key"], item["tag_value"])
            if key in existing_map:
                # Update existing
                lbl = existing_map[key]
                lbl.tag_type = item.get("tag_type", lbl.tag_type)
                lbl.tagged_by = tagged_by or item.get("tagged_by", lbl.tagged_by)
                lbl.tagged_at = datetime.now(timezone.utc)
                created.append(lbl)
            else:
                label = Label(
                    resource_id=resource_id,
                    tag_key=item["tag_key"],
                    tag_value=item["tag_value"],
                    tag_type=item.get("tag_type", "custom"),
                    tagged_by=tagged_by or item.get("tagged_by"),
                    tagged_at=datetime.now(timezone.utc),
                )
                self.session.add(label)
                created.append(label)
        await self.session.flush()
        return created

    async def batch_label(self, operations: list[dict[str, Any]]) -> dict[str, Any]:
        """Batch label operations.

        Each operation: {
            "action": "set" | "patch" | "remove",
            "resource_id": "string",
            "labels": [...],
            "tag_key": "...",  (for remove)
            "tag_value": "...", (for remove, optional)
        }
        """
        results = {"success": [], "errors": []}
        for op in operations:
            try:
                action = op.get("action")
                resource_id = op.get("resource_id")
                if not resource_id:
                    results["errors"].append({"resource_id": resource_id, "error": "Missing resource_id"})
                    continue

                if action == "set":
                    await self.set_labels(resource_id, op.get("labels", []), tagged_by=op.get("tagged_by"))
                    results["success"].append({"resource_id": resource_id, "action": "set"})
                elif action == "patch":
                    await self.patch_labels(resource_id, op.get("labels", []), tagged_by=op.get("tagged_by"))
                    results["success"].append({"resource_id": resource_id, "action": "patch"})
                elif action == "remove":
                    tag_key = op.get("tag_key")
                    tag_value = op.get("tag_value")
                    stmt = select(Label).where(Label.resource_id == resource_id, Label.tag_key == tag_key)
                    if tag_value:
                        stmt = stmt.where(Label.tag_value == tag_value)
                    result = await self.session.execute(stmt)
                    for lbl in result.scalars().all():
                        await self.session.delete(lbl)
                    results["success"].append({"resource_id": resource_id, "action": "remove"})
                else:
                    results["errors"].append({"resource_id": resource_id, "error": f"Unknown action: {action}"})
            except (ValueError, SQLAlchemyError) as e:
                logger.error("Batch label operation failed for resource %s: %s", op.get("resource_id"), e, exc_info=True)
                results["errors"].append({"resource_id": op.get("resource_id"), "error": str(e)})
        await self.session.flush()
        return results

    async def get_label_history(
        self,
        resource_id: str | None = None,
        *,
        tag_key: str | None = None,
        action: str | None = None,
        tagged_by: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[LabelHistory], int]:
        stmt = select(LabelHistory)
        count_stmt = select(func.count()).select_from(LabelHistory)

        if resource_id:
            stmt = stmt.where(LabelHistory.resource_id == resource_id)
            count_stmt = count_stmt.where(LabelHistory.resource_id == resource_id)
        if tag_key:
            stmt = stmt.where(LabelHistory.tag_key == tag_key)
            count_stmt = count_stmt.where(LabelHistory.tag_key == tag_key)
        if action:
            stmt = stmt.where(LabelHistory.action == action)
            count_stmt = count_stmt.where(LabelHistory.action == action)
        if tagged_by:
            stmt = stmt.where(LabelHistory.tagged_by == tagged_by)
            count_stmt = count_stmt.where(LabelHistory.tagged_by == tagged_by)

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(LabelHistory.tagged_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
