"""Label CRUD with JSON sidecar synchronization."""
import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.core.storage import storage
from bids_server.models.database import Label, Resource


class LabelService:
    """Manages labels with DB + JSON sidecar sync."""

    async def set_labels(
        self,
        db: AsyncSession,
        resource_id: str,
        labels: dict[str, Any],
        level: str = "file",
        target_path: Optional[str] = None,
        tagged_by: Optional[str] = None,
    ) -> list[Label]:
        """Replace all labels on a resource."""
        # Delete existing labels
        await db.execute(
            delete(Label).where(Label.resource_id == resource_id)
        )

        # Insert new labels
        created = []
        for key, value in labels.items():
            label = Label(
                resource_id=resource_id,
                level=level,
                target_path=target_path,
                tag_key=key,
                tag_value=str(value) if not isinstance(value, (dict, list)) else json.dumps(value),
                tagged_by=tagged_by,
                tagged_at=datetime.now(timezone.utc),
            )
            db.add(label)
            created.append(label)

        await db.flush()

        # Sync to JSON sidecar
        await self._sync_to_json(db, resource_id, labels)

        return created

    async def patch_labels(
        self,
        db: AsyncSession,
        resource_id: str,
        add: Optional[dict[str, Any]] = None,
        remove: Optional[list[str]] = None,
        tagged_by: Optional[str] = None,
    ) -> list[Label]:
        """Add/update/remove specific labels."""
        # Get existing labels
        result = await db.execute(
            select(Label).where(Label.resource_id == resource_id)
        )
        existing = {row.tag_key: row for row in result.scalars().all()}

        # Remove specified labels
        if remove:
            for key in remove:
                if key in existing:
                    await db.delete(existing[key])
                    del existing[key]

        # Add/update labels
        if add:
            for key, value in add.items():
                tag_value = str(value) if not isinstance(value, (dict, list)) else json.dumps(value)
                if key in existing:
                    existing[key].tag_value = tag_value
                    existing[key].tagged_by = tagged_by
                    existing[key].tagged_at = datetime.now(timezone.utc)
                else:
                    label = Label(
                        resource_id=resource_id,
                        level="file",
                        tag_key=key,
                        tag_value=tag_value,
                        tagged_by=tagged_by,
                        tagged_at=datetime.now(timezone.utc),
                    )
                    db.add(label)

        await db.flush()

        # Rebuild full labels dict and sync to JSON
        result = await db.execute(
            select(Label).where(Label.resource_id == resource_id)
        )
        all_labels = {row.tag_key: row.tag_value for row in result.scalars().all()}
        await self._sync_to_json(db, resource_id, all_labels)

        return list((await db.execute(
            select(Label).where(Label.resource_id == resource_id)
        )).scalars().all())

    async def get_labels(
        self, db: AsyncSession, resource_id: str
    ) -> list[Label]:
        """Get all labels for a resource."""
        result = await db.execute(
            select(Label)
            .where(Label.resource_id == resource_id)
            .order_by(Label.tag_key)
        )
        return list(result.scalars().all())

    async def get_all_tags(self, db: AsyncSession) -> list[dict]:
        """Get all unique tags with counts."""
        from sqlalchemy import func
        result = await db.execute(
            select(
                Label.tag_key,
                func.count(Label.id).label("count"),
            )
            .group_by(Label.tag_key)
            .order_by(Label.tag_key)
        )
        return [{"name": row.tag_key, "count": row.count} for row in result.all()]

    async def _sync_to_json(
        self,
        db: AsyncSession,
        resource_id: str,
        labels: dict[str, Any],
    ):
        """Sync labels to BIDS JSON sidecar file."""
        # Get resource info
        result = await db.execute(
            select(Resource).where(Resource.resource_id == resource_id)
        )
        resource = result.scalar_one_or_none()
        if not resource or not resource.bids_path:
            return

        # Build or update JSON sidecar
        json_path = resource.bids_path
        if not json_path.endswith(".json"):
            # Find the corresponding .json file
            base = json_path.rsplit(".", 1)[0]
            json_path = f"{base}.json"

        # Read existing JSON or create new
        existing = {}
        if storage.file_exists(json_path):
            try:
                data = await storage.read_file(json_path)
                existing = json.loads(data)
            except (json.JSONDecodeError, Exception):
                existing = {}

        # Update VNA.labels section
        if "VNA" not in existing:
            existing["VNA"] = {}
        existing["VNA"]["labels"] = labels

        # Write back
        await storage.write_file(json_path, json.dumps(existing, indent=2, ensure_ascii=False).encode())


# Singleton
label_service = LabelService()
