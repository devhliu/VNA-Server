"""Search service - PostgreSQL full-text search."""

from sqlalchemy import select, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.models.database import Resource, Label


class SearchService:
    """Full-text search using PostgreSQL tsvector."""

    async def search(
        self,
        db: AsyncSession,
        query: str,
        modality: list[str] | None = None,
        subject_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Resource], int]:
        """Full-text search across resources."""
        if self._is_postgres(db):
            return await self._search_pg(db, query, modality, subject_id, limit, offset)
        return await self._search_fallback(db, query, modality, subject_id, limit, offset)

    @staticmethod
    def _is_postgres(db: AsyncSession) -> bool:
        bind = db.get_bind()
        return bind is not None and bind.dialect.name == "postgresql"

    async def _search_fallback(self, db, query, modality, subject_id, limit, offset):
        like_query = f"%{query}%"
        base = select(Resource).where(
            or_(
                Resource.file_name.ilike(like_query),
                Resource.bids_path.ilike(like_query),
                Resource.modality.ilike(like_query),
                Resource.search_vector.ilike(like_query),
            )
        )
        if modality:
            base = base.where(Resource.modality.in_(modality))
        if subject_id:
            base = base.where(Resource.subject_id == subject_id)
        count = (
            await db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar() or 0
        result = await db.execute(base.limit(limit).offset(offset))
        return list(result.scalars().all()), count

    async def _search_pg(self, db, query, modality, subject_id, limit, offset):
        ts_query = func.plainto_tsquery("english", query)
        base = select(Resource).where(Resource.search_vector.op("@@")(ts_query))
        if modality:
            base = base.where(Resource.modality.in_(modality))
        if subject_id:
            base = base.where(Resource.subject_id == subject_id)
        count = (
            await db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar() or 0
        ranked = (
            base.order_by(
                func.ts_rank(Resource.search_vector, ts_query).desc()
            )
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(ranked)
        return list(result.scalars().all()), count

    async def update_search_vector(self, db: AsyncSession, resource_id: str):
        """Update search vector for a resource."""
        result = await db.execute(
            select(Resource).where(Resource.resource_id == resource_id)
        )
        resource = result.scalar_one_or_none()
        if not resource:
            return

        parts = [
            resource.file_name or "",
            resource.modality or "",
            resource.bids_path or "",
        ]
        if resource.metadata_:
            for v in (resource.metadata_ or {}).values():
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, (int, float)):
                    parts.append(str(v))

        label_result = await db.execute(
            select(Label).where(Label.resource_id == resource_id)
        )
        for label in label_result.scalars().all():
            parts.append(label.tag_key)
            if label.tag_value:
                parts.append(str(label.tag_value))

        searchable_text = " ".join(str(p) for p in parts)
        if not self._is_postgres(db):
            resource.search_vector = searchable_text
            await db.flush()
            return

        await db.execute(
            text(
                "UPDATE resources SET search_vector = to_tsvector('english', :text) "
                "WHERE resource_id = :rid"
            ),
            {"text": searchable_text, "rid": resource_id},
        )


# Singleton
search_service = SearchService()
