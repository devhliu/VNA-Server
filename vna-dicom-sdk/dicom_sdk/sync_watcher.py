"""Orthanc change watcher - polls /changes and forwards events to VNA Main Server."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

import httpx

logger = logging.getLogger(__name__)


class ChangeWatcher:
    """Poll Orthanc /changes API and forward events to VNA Main Server.

    This watcher maintains a sequence number to track position in the
    change log, so it only processes new changes on each poll.

    Args:
        dicom_client: DicomClient or AsyncDicomClient instance.
        vna_server_url: URL of VNA Main Server (e.g. http://localhost:8000).
        poll_interval: Seconds between polls (default 5).
        on_change: Optional callback for each change event.
    """

    def __init__(
        self,
        dicom_client: Any,
        vna_server_url: str,
        api_key: str | None = None,
        poll_interval: float = 5.0,
        on_change: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self.dicom = dicom_client
        self.vna_url = vna_server_url.rstrip("/")
        self.api_key = api_key
        self.poll_interval = poll_interval
        self._on_change = on_change
        self._running = False
        self._last_seq = 0

    async def _send_event(self, change_type: str, resource_id: str, resource_type: str) -> None:
        """Forward a change event to the VNA Main Server."""
        event = {
            "source_db": "dicom",
            "event_type": f"resource.{change_type}",
            "resource_id": resource_id,
            "payload": {
                "resource_type": resource_type,
                "source_type": "dicom_only",
                "data_type": "dicom",
            },
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.vna_url}/api/v1/sync/event",
                    json=event,
                    headers=headers or None,
                )
                if resp.is_success:
                    logger.debug("Sent event to VNA: %s %s", change_type, resource_id)
                else:
                    logger.warning("Failed to send event to VNA: %s", resp.status_code)
        except httpx.HTTPError as e:
            logger.error("Error sending event to VNA: %s", e, exc_info=True)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Error building VNA event payload: %s", e, exc_info=True)

        if self._on_change:
            await self._on_change(event)

    async def _process_changes(self) -> None:
        """Fetch and process new changes from Orthanc."""
        try:
            changes = await self.dicom.get_changes(limit=100, since=self._last_seq)
        except (httpx.HTTPError, KeyError) as e:
            logger.error("Error fetching changes from Orthanc: %s", e, exc_info=True)
            return

        content = changes.get("content", [])
        self._last_seq = changes.get("last", self._last_seq)

        for change in content:
            change_type = change.get("ChangeType", "")
            resource_type = change.get("ResourceType", "")
            resource_id = change.get("ID", "")

            if change_type in ("NewInstance", "NewStudy", "NewSeries"):
                await self._send_event("created", resource_id, resource_type)
            elif change_type in ("InstanceUpdated", "StudyUpdated", "SeriesUpdated"):
                await self._send_event("updated", resource_id, resource_type)
            elif change_type in ("InstanceDeleted", "StudyDeleted", "SeriesDeleted"):
                await self._send_event("deleted", resource_id, resource_type)

    async def start(self) -> None:
        """Start the change watcher loop."""
        self._running = True
        logger.info("Starting Orthanc change watcher (VNA: %s)", self.vna_url)

        while self._running:
            await self._process_changes()
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop the change watcher loop."""
        self._running = False
        logger.info("Stopping Orthanc change watcher")


class SyncWatcher:
    """Synchronous version of ChangeWatcher for non-async environments."""

    def __init__(
        self,
        dicom_client: Any,
        vna_server_url: str,
        api_key: str | None = None,
        poll_interval: float = 5.0,
    ) -> None:
        self.dicom = dicom_client
        self.vna_url = vna_server_url.rstrip("/")
        self.api_key = api_key
        self.poll_interval = poll_interval
        self._running = False
        self._last_seq = 0

    def _send_event(self, change_type: str, resource_id: str, resource_type: str) -> None:
        """Forward a change event to the VNA Main Server synchronously."""
        event = {
            "source_db": "dicom",
            "event_type": f"resource.{change_type}",
            "resource_id": resource_id,
            "payload": {
                "resource_type": resource_type,
                "source_type": "dicom_only",
                "data_type": "dicom",
            },
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{self.vna_url}/api/v1/sync/event",
                    json=event,
                    headers=headers or None,
                )
                if resp.is_success:
                    logger.debug("Sent event to VNA: %s %s", change_type, resource_id)
                else:
                    logger.warning("Failed to send event to VNA: %s", resp.status_code)
        except httpx.HTTPError as e:
            logger.error("Error sending event to VNA: %s", e, exc_info=True)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Error building VNA event payload: %s", e, exc_info=True)

    def _process_changes(self) -> None:
        """Fetch and process new changes from Orthanc."""
        try:
            changes = self.dicom.get_changes(limit=100, since=self._last_seq)
        except (httpx.HTTPError, KeyError) as e:
            logger.error("Error fetching changes from Orthanc: %s", e, exc_info=True)
            return

        content = changes.get("content", [])
        self._last_seq = changes.get("last", self._last_seq)

        for change in content:
            change_type = change.get("ChangeType", "")
            resource_type = change.get("ResourceType", "")
            resource_id = change.get("ID", "")

            if change_type in ("NewInstance", "NewStudy", "NewSeries"):
                self._send_event("created", resource_id, resource_type)
            elif change_type in ("InstanceUpdated", "StudyUpdated", "SeriesUpdated"):
                self._send_event("updated", resource_id, resource_type)
            elif change_type in ("InstanceDeleted", "StudyDeleted", "SeriesDeleted"):
                self._send_event("deleted", resource_id, resource_type)

    def start(self) -> None:
        """Start the change watcher loop (blocking)."""
        import time
        self._running = True
        logger.info("Starting Orthanc sync watcher (VNA: %s)", self.vna_url)

        while self._running:
            self._process_changes()
            time.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop the change watcher loop."""
        self._running = False
        logger.info("Stopping Orthanc sync watcher")
