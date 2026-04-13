"""Database sync service - receive events from DICOM/BIDS servers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.config import settings
from vna_main.models.database import PatientMapping, ResourceIndex, SyncEvent
from vna_main.services.routing_service import RoutingService
from vna_main.services.http_client import get_http_client

logger = logging.getLogger(__name__)


def _bids_request_headers() -> dict[str, str] | None:
    if not settings.BIDS_SERVER_API_KEY:
        return None
    return {"Authorization": f"Bearer {settings.BIDS_SERVER_API_KEY}"}


class SyncService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register_server(self, source_db: str, url: str) -> dict[str, Any]:
        """Register a DICOM or BIDS server (stored as a sync event for tracking)."""
        event = SyncEvent(
            source_db=source_db,
            event_type="registered",
            resource_id="__server__",
            payload={"url": url, "action": "register"},
            processed=True,
        )
        self.session.add(event)
        await self.session.flush()
        return {"source_db": source_db, "url": url, "status": "registered"}

    async def get_status(self) -> dict[str, Any]:
        """Get sync status for all registered servers."""
        # Get distinct source_dbs
        stmt = select(SyncEvent.source_db).distinct()
        result = await self.session.execute(stmt)
        source_dbs = [row[0] for row in result.all()]

        servers = {}
        for db_name in source_dbs:
            total = (await self.session.execute(
                select(func.count()).select_from(SyncEvent).where(
                    SyncEvent.source_db == db_name,
                )
            )).scalar() or 0
            pending = (await self.session.execute(
                select(func.count()).select_from(SyncEvent).where(
                    SyncEvent.source_db == db_name,
                    SyncEvent.processed == False,  # noqa: E712
                )
            )).scalar() or 0
            servers[db_name] = {
                "total_events": total,
                "pending_events": pending,
            }

        total_pending = (await self.session.execute(
            select(func.count()).select_from(SyncEvent).where(
                SyncEvent.processed == False,  # noqa: E712
            )
        )).scalar() or 0

        return {
            "servers": servers,
            "total_pending": total_pending,
        }

    async def trigger_sync(self, source_db: str | None = None) -> dict[str, Any]:
        """Process pending sync events from sub-servers.

        For each unprocessed event:
        - 'dicom_received' / 'study_stable' → fetch study metadata from DICOM
          server via httpx, upsert into resource_index, auto-create patient mapping
        - 'bids_completed' → fetch conversion result from BIDS server, update index
        - 'resource.created' → add/update resource in index
        - 'resource.updated' → update resource metadata
        - 'resource.deleted' → remove resource from index
        - 'label.updated'    → mark event processed (label sync handled elsewhere)

        Events are processed in creation order and marked as processed.
        """
        stmt = select(SyncEvent).where(
            SyncEvent.processed == False,  # noqa: E712
        )
        if source_db:
            stmt = stmt.where(SyncEvent.source_db == source_db)
        stmt = stmt.order_by(SyncEvent.created_at.asc()).limit(100)

        result = await self.session.execute(stmt)
        pending_events = list(result.scalars().all())

        processed_count = 0
        errors: list[dict[str, Any]] = []

        for event in pending_events:
            try:
                await self._process_event(event)
                event.processed = True
                processed_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to process sync event %s (type=%s, source=%s): %s",
                    event.id, event.event_type, event.source_db, exc,
                    exc_info=True,
                )
                errors.append({
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "error": str(exc),
                })

        await self.session.flush()
        return {
            "triggered": True,
            "processed_events": processed_count,
            "total_pending": len(pending_events),
            "errors": errors,
            "source_db": source_db,
        }

    async def _process_event(self, event: SyncEvent) -> None:
        """Process a single sync event and update the resource index."""
        payload = event.payload or {}
        event_type = event.event_type
        resource_id = event.resource_id

        # --- DICOM webhook events (from Orthanc Lua integration) ---
        if event_type in ("dicom_received", "study_stable"):
            await self._process_dicom_event(event, payload, resource_id)

        # --- BIDS webhook events ---
        elif event_type == "bids_completed":
            await self._process_bids_event(event, payload, resource_id)

        # --- Generic resource CRUD events ---
        elif event_type == "resource.created":
            existing = (await self.session.execute(
                select(ResourceIndex).where(ResourceIndex.resource_id == resource_id)
            )).scalar_one_or_none()

            if existing is None:
                resource = ResourceIndex(
                    resource_id=resource_id,
                    source_type=payload.get("source_type", f"{event.source_db}_only"),
                    data_type=payload.get("data_type", event.source_db),
                    dicom_study_uid=payload.get("dicom_study_uid"),
                    dicom_series_uid=payload.get("dicom_series_uid"),
                    dicom_sop_uid=payload.get("dicom_sop_uid"),
                    bids_subject_id=payload.get("bids_subject_id"),
                    bids_session_id=payload.get("bids_session_id"),
                    bids_path=payload.get("bids_path"),
                    file_name=payload.get("file_name"),
                    file_size=payload.get("file_size"),
                    content_hash=payload.get("content_hash"),
                    metadata_=payload.get("metadata"),
                )
                self.session.add(resource)
            else:
                for field in ("source_type", "data_type", "dicom_study_uid",
                              "dicom_series_uid", "dicom_sop_uid", "bids_subject_id",
                              "bids_session_id", "bids_path", "file_name",
                              "file_size", "content_hash"):
                    if field in payload:
                        setattr(existing, field, payload[field])
                if "metadata" in payload:
                    existing.metadata_ = payload["metadata"]

        elif event_type == "resource.updated":
            existing = (await self.session.execute(
                select(ResourceIndex).where(ResourceIndex.resource_id == resource_id)
            )).scalar_one_or_none()
            if existing:
                for field in ("source_type", "data_type", "dicom_study_uid",
                              "dicom_series_uid", "dicom_sop_uid", "bids_subject_id",
                              "bids_session_id", "bids_path", "file_name",
                              "file_size", "content_hash"):
                    if field in payload:
                        setattr(existing, field, payload[field])
                if "metadata" in payload:
                    existing.metadata_ = payload["metadata"]

        elif event_type == "resource.deleted":
            await self.session.execute(
                delete(ResourceIndex).where(ResourceIndex.resource_id == resource_id)
            )

        elif event_type in ("label.updated", "rebuild_requested"):
            logger.debug("Event %s type %s requires no processing", event.id, event_type)

        else:
            logger.info("Unknown sync event type '%s' for event %s, marking processed", event_type, event.id)

    async def _process_dicom_event(
        self, event: SyncEvent, payload: dict, resource_id: str
    ) -> None:
        """Handle dicom_received / study_stable events.

        Fetches study metadata from the DICOM server via httpx, upserts
        into resource_index, and auto-creates patient mapping when needed.
        """
        orthanc_study_id = payload.get("orthanc_study_id") or resource_id
        dicom_url = settings.DICOM_SERVER_URL

        try:
            client = await get_http_client()
            resp = await client.get(f"{dicom_url}/studies/{orthanc_study_id}")
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
            logger.error(
                "Failed to fetch study %s from DICOM server: %s", orthanc_study_id, exc,
                exc_info=True,
            )
            # Fall back to using payload data directly
            data = payload.get("metadata", {})

        tags = data.get("MainDicomTags", {})
        patient_tags = data.get("PatientMainDicomTags", {})
        study_uid = tags.get("StudyInstanceUID", orthanc_study_id)

        # Build metadata dict from the response
        metadata = {
            "orthanc_study_id": orthanc_study_id,
            "study_description": tags.get("StudyDescription"),
            "patient_id": patient_tags.get("PatientID"),
            "patient_name": patient_tags.get("PatientName"),
            "study_date": tags.get("StudyDate"),
            "accession_number": tags.get("AccessionNumber"),
            "modalities": tags.get("ModalitiesInStudy"),
            "institution": tags.get("InstitutionName"),
        }
        # Merge any extra metadata from payload
        if payload.get("metadata"):
            metadata.update(payload["metadata"])

        # Upsert resource
        existing = (await self.session.execute(
            select(ResourceIndex).where(
                ResourceIndex.dicom_study_uid == study_uid,
            )
        )).scalar_one_or_none()

        if existing is None:
            existing = ResourceIndex(
                resource_id=resource_id or f"dicom-{orthanc_study_id[:12]}",
                source_type=payload.get("source_type", "dicom_only"),
                data_type="dicom",
                dicom_study_uid=study_uid,
                file_name=f"Study_{orthanc_study_id}",
                metadata_=metadata,
            )
            self.session.add(existing)
        else:
            existing.metadata_ = metadata
            if payload.get("source_type"):
                existing.source_type = payload["source_type"]

        # Auto-create patient mapping if not exists
        patient_id = patient_tags.get("PatientID") or metadata.get("patient_id")
        if patient_id:
            # Validate PatientID before auto-creating
            patient_id = patient_id.strip()
            if len(patient_id) < 1 or len(patient_id) > 256:
                logger.warning("Skipping auto patient creation: invalid PatientID length: %r", patient_id)
            else:
                existing_patient = (await self.session.execute(
                    select(PatientMapping).where(PatientMapping.hospital_id == patient_id)
                )).scalar_one_or_none()

                if existing_patient is None:
                    logger.warning("Auto-creating patient mapping for PatientID: %r", patient_id)
                    new_patient = PatientMapping(
                        hospital_id=patient_id,
                        source="dicom_auto",
                        external_system="orthanc",
                    )
                    self.session.add(new_patient)
                    await self.session.flush()
                    existing.patient_ref = new_patient.patient_ref
                elif existing.patient_ref is None:
                    existing.patient_ref = existing_patient.patient_ref

    async def _process_bids_event(
        self, event: SyncEvent, payload: dict, resource_id: str
    ) -> None:
        """Handle bids_completed events.

        Calls BIDS server to fetch conversion result, updates resource_index.
        """
        bids_resource_id = payload.get("bids_resource_id") or resource_id
        bids_url = settings.BIDS_SERVER_URL

        try:
            client = await get_http_client()
            resp = await client.post(
                f"{bids_url}/api/query",
                headers=_bids_request_headers(),
                json={"resource_id": bids_resource_id},
            )
            if resp.is_success:
                bids_data = resp.json()
                if isinstance(bids_data, list) and bids_data:
                    bids_data = bids_data[0]
                payload["bids_data"] = bids_data
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
            logger.error(
                "Failed to fetch BIDS resource %s from BIDS server: %s",
                bids_resource_id, exc,
                exc_info=True,
            )

        # Upsert into resource_index
        existing = (await self.session.execute(
            select(ResourceIndex).where(
                ResourceIndex.bids_path == payload.get("bids_path"),
            )
        )).scalar_one_or_none() if payload.get("bids_path") else None

        if existing is None and resource_id:
            existing = (await self.session.execute(
                select(ResourceIndex).where(ResourceIndex.resource_id == resource_id)
            )).scalar_one_or_none()

        bids_data = payload.get("bids_data", {})
        if existing is None:
            existing = ResourceIndex(
                resource_id=resource_id or f"bids-{bids_resource_id[:12]}",
                source_type=payload.get("source_type", "bids_only"),
                data_type=payload.get("modality", bids_data.get("modality", "nifti")),
                bids_subject_id=payload.get("subject_id", bids_data.get("subject_id")),
                bids_session_id=payload.get("session_id", bids_data.get("session_id")),
                bids_path=payload.get("bids_path", bids_data.get("bids_path")),
                file_name=payload.get("file_name", bids_data.get("file_name")),
                file_size=payload.get("file_size", bids_data.get("file_size")),
                content_hash=payload.get("content_hash", bids_data.get("content_hash")),
                metadata_={"bids_resource_id": bids_resource_id, **(bids_data.get("metadata", {}))},
            )
            self.session.add(existing)
        else:
            if payload.get("bids_path"):
                existing.bids_path = payload["bids_path"]
            if payload.get("file_size"):
                existing.file_size = payload["file_size"]
            if payload.get("content_hash"):
                existing.content_hash = payload["content_hash"]
            # Promote source_type if now both DICOM and BIDS data exists
            if existing.source_type == "dicom_only" and existing.bids_path:
                existing.source_type = "dicom_and_bids"
            elif existing.source_type == "bids_only" and existing.dicom_study_uid:
                existing.source_type = "dicom_and_bids"

    async def receive_event(self, event_data: dict[str, Any]) -> SyncEvent:
        """Receive a sync event from a sub-server."""
        event = SyncEvent(
            source_db=event_data["source_db"],
            event_type=event_data["event_type"],
            resource_id=event_data["resource_id"],
            payload=event_data.get("payload"),
            processed=False,
        )
        self.session.add(event)
        await self.session.flush()
        # Explicitly ensure processed is False after flush
        if event.processed is not False:
            raise RuntimeError(f"Data integrity error: sync event {event.id} expected processed=False, got {event.processed}")
        return event

    async def list_events(
        self,
        *,
        source_db: str | None = None,
        event_type: str | None = None,
        processed: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[SyncEvent], int]:
        stmt = select(SyncEvent)
        count_stmt = select(func.count()).select_from(SyncEvent)

        if source_db:
            stmt = stmt.where(SyncEvent.source_db == source_db)
            count_stmt = count_stmt.where(SyncEvent.source_db == source_db)
        if event_type:
            stmt = stmt.where(SyncEvent.event_type == event_type)
            count_stmt = count_stmt.where(SyncEvent.event_type == event_type)
        if processed is not None:
            stmt = stmt.where(SyncEvent.processed == processed)
            count_stmt = count_stmt.where(SyncEvent.processed == processed)

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.offset(offset).limit(limit).order_by(SyncEvent.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def verify_consistency(
        self,
        *,
        dicom_url: str | None = None,
        bids_url: str | None = None,
        repair: bool = False,
    ) -> dict[str, Any]:
        """Summarize current sync consistency state across index and sub-services."""
        routing = RoutingService(dicom_url=dicom_url, bids_url=bids_url)
        dicom_health = await routing.health_check_dicom()
        bids_health = await routing.health_check_bids()

        pending_events = (await self.session.execute(
            select(func.count()).select_from(SyncEvent).where(SyncEvent.processed == False)  # noqa: E712
        )).scalar() or 0
        total_resources = (await self.session.execute(
            select(func.count()).select_from(ResourceIndex)
        )).scalar() or 0
        unlinked_resources = (await self.session.execute(
            select(func.count()).select_from(ResourceIndex).where(
                ResourceIndex.source_type == "dicom_and_bids",
                ResourceIndex.dicom_study_uid.is_(None),
            )
        )).scalar() or 0

        issues: list[dict[str, Any]] = []
        if dicom_health["status"] != "healthy":
            issues.append({"component": "dicom", "issue": dicom_health.get("error", "unhealthy")})
        if bids_health["status"] != "healthy":
            issues.append({"component": "bids", "issue": bids_health.get("error", "unhealthy")})
        if pending_events:
            issues.append({"component": "sync_events", "issue": f"{pending_events} pending events"})
        if unlinked_resources:
            issues.append({"component": "resource_index", "issue": f"{unlinked_resources} unlinked combined resources"})

        repaired = 0
        if repair and pending_events:
            # Instead of deleting unprocessed events, trigger reprocessing of them
            # We'll reset the processed flag to False for a limited set of events to reprocess
            from sqlalchemy import update
            # Limit reprocessing to prevent overwhelming the system
            stmt = (
                update(SyncEvent)
                .where(SyncEvent.processed == True)  # Only reset previously processed events
                .order_by(SyncEvent.created_at.desc())
                .limit(min(pending_events, 100))  # Process at most 100 events at a time
                .values(processed=False)
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            repaired = result.rowcount
            # Trigger processing of the reset events
            trigger_result = await self.trigger_sync()
            repaired = trigger_result.get("processed_events", 0)

        return {
            "status": "healthy" if not issues else "degraded",
            "summary": {
                "total_resources": total_resources,
                "pending_events": pending_events,
                "issues_found": len(issues),
                "repaired_events": repaired,
            },
            "checks": {
                "dicom": dicom_health,
                "bids": bids_health,
            },
            "issues": issues,
        }

    async def rebuild_index(
        self,
        *,
        dicom_url: str | None = None,
        bids_url: str | None = None,
        clear_existing: bool = False,
    ) -> dict[str, Any]:
        """Rebuild the main DB index by pulling data from sub-servers.

        If clear_existing is True, all existing resource index entries are
        removed first. Then the service queries each sub-server for its
        current resources and upserts them into the resource index.
        """
        if clear_existing:
            await self.session.execute(delete(ResourceIndex))

        routing = RoutingService(dicom_url=dicom_url, bids_url=bids_url)
        results: dict[str, Any] = {}

        # Rebuild from DICOM server
        try:
            dicom_studies = await self._fetch_dicom_resources(routing)
            results["dicom"] = {"fetched": len(dicom_studies), "status": "ok"}
        except Exception as exc:
            logger.error("Failed to fetch DICOM resources during rebuild: %s", exc, exc_info=True)
            dicom_studies = []
            results["dicom"] = {"fetched": 0, "status": "error", "error": str(exc)}

        # Rebuild from BIDS server
        try:
            bids_resources = await self._fetch_bids_resources(routing)
            results["bids"] = {"fetched": len(bids_resources), "status": "ok"}
        except Exception as exc:
            logger.error("Failed to fetch BIDS resources during rebuild: %s", exc, exc_info=True)
            bids_resources = []
            results["bids"] = {"fetched": 0, "status": "error", "error": str(exc)}

        # Upsert all fetched resources
        total_upserted = 0
        for res_data in dicom_studies + bids_resources:
            rid = res_data.get("resource_id")
            if not rid:
                continue
            existing = (await self.session.execute(
                select(ResourceIndex).where(ResourceIndex.resource_id == rid)
            )).scalar_one_or_none()

            # Separate metadata from column data
            meta = res_data.pop("metadata", None)
            col_data = {k: v for k, v in res_data.items() if k in ResourceIndex.__table__.columns.keys()}

            if existing:
                for field, value in col_data.items():
                    setattr(existing, field, value)
                if meta:
                    existing.metadata_ = meta
            else:
                if meta:
                    col_data["metadata_"] = meta
                self.session.add(ResourceIndex(**col_data))
            # Restore metadata for next iteration
            if meta:
                res_data["metadata"] = meta
            total_upserted += 1

        # Record rebuild as a sync event for audit
        event = SyncEvent(
            source_db="main",
            event_type="rebuild_completed",
            resource_id="__rebuild__",
            payload={
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "clear_existing": clear_existing,
                "total_upserted": total_upserted,
                "results": results,
            },
            processed=True,
        )
        self.session.add(event)
        await self.session.flush()

        return {
            "rebuild_completed": True,
            "clear_existing": clear_existing,
            "total_upserted": total_upserted,
            "results": results,
        }

    async def _fetch_dicom_resources(self, routing: RoutingService) -> list[dict[str, Any]]:
        """Fetch all studies from the DICOM server and convert to resource index format."""
        resources = []
        try:
            client = await get_http_client()
            resp = await client.get(f"{routing.dicom_url}/studies")
            resp.raise_for_status()
            study_ids = resp.json()

            # Batch fetch study details for better performance
            tasks = [client.get(f"{routing.dicom_url}/studies/{sid}") for sid in study_ids]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for sid, response in zip(study_ids, responses):
                if isinstance(response, BaseException):
                    logger.debug("Skipping study %s due to fetch error: %s", sid, response)
                    continue
                    
                try:
                    detail = response
                    detail.raise_for_status()
                    data = detail.json()
                    tags = data.get("MainDicomTags", {})
                    patient_tags = data.get("PatientMainDicomTags", {})
                    study_uid = tags.get("StudyInstanceUID", sid)

                    # Auto-create patient mapping if not exists
                    patient_id = patient_tags.get("PatientID")
                    if patient_id:
                        existing_patient = (await self.session.execute(
                            select(PatientMapping).where(PatientMapping.hospital_id == patient_id)
                        )).scalar_one_or_none()
                        if existing_patient is None:
                            new_patient = PatientMapping(
                                hospital_id=patient_id,
                                source="dicom_auto",
                                external_system="orthanc",
                            )
                            self.session.add(new_patient)
                            await self.session.flush()

                    resources.append({
                        "resource_id": f"dicom-{sid[:12]}",
                        "source_type": "dicom_only",
                        "data_type": "dicom",
                        "dicom_study_uid": study_uid,
                        "file_name": f"{study_uid}.dcm",
                        "metadata": {
                            "orthanc_study_id": sid,
                            "patient_id": patient_tags.get("PatientID"),
                            "patient_name": patient_tags.get("PatientName"),
                            "study_date": tags.get("StudyDate"),
                            "study_description": tags.get("StudyDescription"),
                            "modalities": tags.get("ModalitiesInStudy"),
                            "institution": tags.get("InstitutionName"),
                            "accession_number": tags.get("AccessionNumber"),
                        },
                    })
                except Exception:
                    logger.debug("Skipping study %s due to fetch error", sid)
                    continue
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error("DICOM fetch failed: %s", exc, exc_info=True)
            raise
        return resources

    async def _fetch_bids_resources(self, routing: RoutingService) -> list[dict[str, Any]]:
        """Fetch all resources from the BIDS server and convert to resource index format."""
        resources = []
        try:
            client = await get_http_client()
            resp = await client.post(
                f"{routing.bids_url}/api/query",
                headers=_bids_request_headers(),
                json={"limit": 10000},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("resources", data) if isinstance(data, dict) else data

            for item in items:
                if isinstance(item, dict):
                    resources.append({
                        "resource_id": item.get("resource_id", f"bids-{item.get('id', '')}"),
                        "source_type": "bids_only",
                        "data_type": "nifti",
                        "bids_subject_id": item.get("subject_id"),
                        "bids_session_id": item.get("session_id"),
                        "bids_path": item.get("bids_path"),
                        "file_name": item.get("file_name"),
                        "file_size": item.get("file_size"),
                        "content_hash": item.get("content_hash"),
                        "metadata": {"bids_resource_id": item.get("resource_id")},
                    })
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error("BIDS fetch failed: %s", exc, exc_info=True)
            raise
        return resources
