"""Synchronous VNA Main Server client."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from vna_main_sdk.models import (
    BatchLabelOperation,
    DataType,
    HealthStatus,
    Label,
    LabelHistoryEntry,
    LabelHistoryResult,
    Patient,
    PatientSyncStatus,
    QueryResult,
    Resource,
    ServerRegistration,
    SourceType,
    SyncStatus,
    TagInfo,
    WebhookDelivery,
    WebhookStats,
    WebhookSubscription,
)

logger = logging.getLogger(__name__)


class VnaClientError(Exception):
    """VNA client error."""

    def __init__(self, message: str, status_code: Optional[int] = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class VnaClient:
    """Synchronous client for the VNA Main Server.

    Args:
        base_url: Base URL of the VNA Main Server.
        api_key: Optional API key for authentication.
        timeout: Request timeout in seconds.
        verify_ssl: Whether to verify SSL certificates.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._headers,
            timeout=timeout,
            verify=verify_ssl,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> VnaClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        """Make an HTTP request and handle errors."""
        try:
            resp = self._client.request(method, path, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            detail = None
            try:
                detail = e.response.json()
            except (json.JSONDecodeError, ValueError):
                detail = e.response.text
            raise VnaClientError(
                f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
                status_code=e.response.status_code,
                detail=detail,
            ) from e
        except httpx.RequestError as e:
            raise VnaClientError(f"Request failed: {e}") from e

    # ─── Resources ─────────────────────────────────────────────────────────

    def list_resources(
        self,
        patient_ref: Optional[str] = None,
        data_type: Optional[str | DataType] = None,
        source_type: Optional[str | SourceType] = None,
        labels: Optional[dict[str, Optional[str]]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> QueryResult:
        """List resources with optional filters.

        Args:
            patient_ref: Filter by patient reference.
            data_type: Filter by data type.
            source_type: Filter by source type.
            labels: Filter by labels (key-value pairs).
            limit: Maximum number of results.
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if patient_ref is not None:
            params["patient_ref"] = patient_ref
        if data_type is not None:
            params["data_type"] = str(data_type) if isinstance(data_type, DataType) else data_type
        if source_type is not None:
            params["source_type"] = str(source_type) if isinstance(source_type, SourceType) else source_type
        if labels:
            params["labels"] = labels
        resp = self._request("GET", "/api/v1/resources", params=params)
        return QueryResult.model_validate(resp.json())

    def get_resource(self, resource_id: str) -> Resource:
        """Get a resource by ID with merged DICOM+BIDS view.

        Args:
            resource_id: The resource identifier.
        """
        resp = self._request("GET", f"/api/v1/resources/{resource_id}")
        return Resource.model_validate(resp.json())

    def register_resource(
        self,
        patient_ref: str,
        source_type: str | SourceType,
        dicom_study_uid: Optional[str] = None,
        dicom_series_uid: Optional[str] = None,
        bids_path: Optional[str] = None,
        bids_subject: Optional[str] = None,
        bids_session: Optional[str] = None,
        bids_datatype: Optional[str] = None,
        data_type: Optional[str | DataType] = None,
        labels: Optional[dict[str, Optional[str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Resource:
        """Register a new resource.

        Args:
            patient_ref: Patient reference.
            source_type: Source type (dicom or bids).
            dicom_study_uid: DICOM Study Instance UID.
            dicom_series_uid: DICOM Series Instance UID.
            bids_path: BIDS file path.
            bids_subject: BIDS subject ID.
            bids_session: BIDS session ID.
            bids_datatype: BIDS datatype (e.g. anat, func).
            data_type: Data type classification.
            labels: Initial labels.
            metadata: Additional metadata.
        """
        body: dict[str, Any] = {
            "patient_ref": patient_ref,
            "source_type": str(source_type) if isinstance(source_type, SourceType) else source_type,
        }
        if dicom_study_uid is not None:
            body["dicom_study_uid"] = dicom_study_uid
        if dicom_series_uid is not None:
            body["dicom_series_uid"] = dicom_series_uid
        if bids_path is not None:
            body["bids_path"] = bids_path
        if bids_subject is not None:
            body["bids_subject"] = bids_subject
        if bids_session is not None:
            body["bids_session"] = bids_session
        if bids_datatype is not None:
            body["bids_datatype"] = bids_datatype
        if data_type is not None:
            body["data_type"] = str(data_type) if isinstance(data_type, DataType) else data_type
        if labels is not None:
            body["labels"] = labels
        if metadata is not None:
            body["metadata"] = metadata
        resp = self._request("POST", "/api/v1/resources", json=body)
        return Resource.model_validate(resp.json())

    def update_resource(
        self,
        resource_id: str,
        patient_ref: Optional[str] = None,
        source_type: Optional[str | SourceType] = None,
        dicom_study_uid: Optional[str] = None,
        dicom_series_uid: Optional[str] = None,
        bids_path: Optional[str] = None,
        bids_subject: Optional[str] = None,
        bids_session: Optional[str] = None,
        bids_datatype: Optional[str] = None,
        data_type: Optional[str | DataType] = None,
        labels: Optional[dict[str, Optional[str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Resource:
        """Update an existing resource.

        Args:
            resource_id: The resource identifier.
        """
        body: dict[str, Any] = {}
        if patient_ref is not None:
            body["patient_ref"] = patient_ref
        if source_type is not None:
            body["source_type"] = str(source_type) if isinstance(source_type, SourceType) else source_type
        if dicom_study_uid is not None:
            body["dicom_study_uid"] = dicom_study_uid
        if dicom_series_uid is not None:
            body["dicom_series_uid"] = dicom_series_uid
        if bids_path is not None:
            body["bids_path"] = bids_path
        if bids_subject is not None:
            body["bids_subject"] = bids_subject
        if bids_session is not None:
            body["bids_session"] = bids_session
        if bids_datatype is not None:
            body["bids_datatype"] = bids_datatype
        if data_type is not None:
            body["data_type"] = str(data_type) if isinstance(data_type, DataType) else data_type
        if labels is not None:
            body["labels"] = labels
        if metadata is not None:
            body["metadata"] = metadata
        resp = self._request("PATCH", f"/api/v1/resources/{resource_id}", json=body)
        return Resource.model_validate(resp.json())

    def delete_resource(self, resource_id: str) -> dict[str, Any]:
        """Delete a resource from the index.

        Args:
            resource_id: The resource identifier.
        """
        resp = self._request("DELETE", f"/api/v1/resources/{resource_id}")
        return resp.json()

    # ─── Patients ──────────────────────────────────────────────────────────

    def get_patient(self, patient_ref: str) -> Patient:
        """Get a patient with all resources.

        Args:
            patient_ref: The patient reference.
        """
        resp = self._request("GET", f"/api/v1/patients/{patient_ref}")
        return Patient.model_validate(resp.json())

    def list_patients(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List patients.

        Args:
            limit: Maximum number of results.
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        resp = self._request("GET", "/api/v1/patients", params=params)
        return resp.json()

    def create_patient(
        self,
        patient_ref: str,
        hospital_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Patient:
        """Create a patient ID mapping.

        Args:
            patient_ref: Patient reference.
            hospital_id: Hospital patient ID.
            source: Hospital/source identifier.
        """
        body: dict[str, Any] = {"patient_ref": patient_ref}
        if hospital_id is not None:
            body["hospital_id"] = hospital_id
        if source is not None:
            body["source"] = source
        resp = self._request("POST", "/api/v1/patients", json=body)
        return Patient.model_validate(resp.json())

    def update_patient(
        self,
        patient_ref: str,
        hospital_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Patient:
        """Update a patient mapping.

        Args:
            patient_ref: The patient reference.
            hospital_id: New hospital patient ID.
            source: New hospital/source identifier.
        """
        body: dict[str, Any] = {}
        if hospital_id is not None:
            body["hospital_id"] = hospital_id
        if source is not None:
            body["source"] = source
        resp = self._request("PATCH", f"/api/v1/patients/{patient_ref}", json=body)
        return Patient.model_validate(resp.json())

    # ─── Labels ────────────────────────────────────────────────────────────

    def get_labels(self, resource_id: str) -> list[Label]:
        """Get labels for a resource.

        Args:
            resource_id: The resource identifier.
        """
        resp = self._request("GET", f"/api/v1/resources/{resource_id}/labels")
        data = resp.json()
        if isinstance(data, list):
            return [Label.model_validate(l) for l in data]
        return [Label.model_validate(l) for l in data.get("labels", [])]

    def set_labels(
        self, resource_id: str, labels: dict[str, Optional[str]]
    ) -> list[Label]:
        """Set labels for a resource (replaces existing).

        Args:
            resource_id: The resource identifier.
            labels: Dictionary of label key-value pairs.
        """
        resp = self._request(
            "PUT",
            f"/api/v1/resources/{resource_id}/labels",
            json={"labels": labels},
        )
        data = resp.json()
        if isinstance(data, list):
            return [Label.model_validate(l) for l in data]
        return [Label.model_validate(l) for l in data.get("labels", [])]

    def patch_labels(
        self,
        resource_id: str,
        add: Optional[dict[str, Optional[str]]] = None,
        remove: Optional[list[str]] = None,
    ) -> list[Label]:
        """Patch labels for a resource (add/remove).

        Args:
            resource_id: The resource identifier.
            add: Labels to add or update.
            remove: Label keys to remove.
        """
        body: dict[str, Any] = {}
        if add:
            body["add"] = add
        if remove:
            body["remove"] = remove
        resp = self._request(
            "PATCH",
            f"/api/v1/resources/{resource_id}/labels",
            json=body,
        )
        data = resp.json()
        if isinstance(data, list):
            return [Label.model_validate(l) for l in data]
        return [Label.model_validate(l) for l in data.get("labels", [])]

    def list_all_tags(self) -> list[TagInfo]:
        """List all tags with counts."""
        resp = self._request("GET", "/api/v1/labels/tags")
        data = resp.json()
        if isinstance(data, list):
            return [TagInfo.model_validate(t) for t in data]
        return [TagInfo.model_validate(t) for t in data.get("tags", [])]

    def batch_label(self, operations: list[BatchLabelOperation]) -> dict[str, Any]:
        """Execute batch label operations.

        Args:
            operations: List of batch label operations.
        """
        resp = self._request(
            "POST",
            "/api/v1/labels/batch",
            json={"operations": [op.model_dump() for op in operations]},
        )
        return resp.json()

    # ─── Query ─────────────────────────────────────────────────────────────

    def query(
        self,
        patient_ref: Optional[str] = None,
        data_type: Optional[str | DataType] = None,
        source_type: Optional[str | SourceType] = None,
        labels: Optional[dict[str, Optional[str]]] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> QueryResult:
        """Unified query across all data sources.

        Args:
            patient_ref: Filter by patient reference.
            data_type: Filter by data type.
            source_type: Filter by source type.
            labels: Filter by labels.
            search: Full-text search string.
            limit: Maximum number of results.
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if patient_ref is not None:
            params["patient_ref"] = patient_ref
        if data_type is not None:
            params["data_type"] = str(data_type) if isinstance(data_type, DataType) else data_type
        if source_type is not None:
            params["source_type"] = str(source_type) if isinstance(source_type, SourceType) else source_type
        if labels:
            params["labels"] = labels
        if search is not None:
            params["search"] = search
        resp = self._request("GET", "/api/v1/query", params=params)
        return QueryResult.model_validate(resp.json())

    # ─── Server Management ─────────────────────────────────────────────────

    def register_server(
        self,
        server_type: str,
        url: str,
        name: str,
    ) -> ServerRegistration:
        """Register a DICOM or BIDS server.

        Args:
            server_type: Server type (e.g. 'dicom', 'bids').
            url: Server URL.
            name: Server name.
        """
        body = {"server_type": server_type, "url": url, "name": name}
        resp = self._request("POST", "/api/v1/servers", json=body)
        return ServerRegistration.model_validate(resp.json())

    # ─── Sync ──────────────────────────────────────────────────────────────

    def sync_status(self) -> SyncStatus:
        """Get sync status."""
        resp = self._request("GET", "/api/v1/sync/status")
        return SyncStatus.model_validate(resp.json())

    def trigger_sync(self, source: str | SourceType) -> SyncStatus:
        """Trigger manual sync.

        Args:
            source: Sync source ('dicom' or 'bids').
        """
        body = {"source": str(source) if isinstance(source, SourceType) else source}
        resp = self._request("POST", "/api/v1/sync/trigger", json=body)
        return SyncStatus.model_validate(resp.json())

    # ─── Health ────────────────────────────────────────────────────────────

    def health(self) -> HealthStatus:
        """Health check."""
        resp = self._request("GET", "/api/v1/health")
        return HealthStatus.model_validate(resp.json())

    # ─── Webhooks ─────────────────────────────────────────────────────────

    def create_webhook(
        self,
        url: str,
        events: list[str],
        description: Optional[str] = None,
        secret: Optional[str] = None,
        enabled: bool = True,
    ) -> WebhookSubscription:
        """Create a webhook subscription.

        Args:
            url: Webhook target URL.
            events: List of event types to subscribe to.
            description: Optional description.
            secret: Optional HMAC secret for signature verification.
            enabled: Whether the webhook is enabled.
        """
        body: dict[str, Any] = {"url": url, "events": events}
        if description is not None:
            body["description"] = description
        if secret is not None:
            body["secret"] = secret
        body["enabled"] = enabled
        resp = self._request("POST", "/api/v1/webhooks", json=body)
        return WebhookSubscription.model_validate(resp.json())

    def get_webhook(self, webhook_id: int) -> WebhookSubscription:
        """Get a webhook subscription by ID.

        Args:
            webhook_id: The webhook ID.
        """
        resp = self._request("GET", f"/api/v1/webhooks/{webhook_id}")
        return WebhookSubscription.model_validate(resp.json())

    def list_webhooks(
        self,
        event: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> list[WebhookSubscription]:
        """List webhook subscriptions.

        Args:
            event: Filter by event type.
            enabled: Filter by enabled status.
        """
        params: dict[str, Any] = {}
        if event is not None:
            params["event"] = event
        if enabled is not None:
            params["enabled"] = str(enabled).lower()
        resp = self._request("GET", "/api/v1/webhooks", params=params)
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        return [WebhookSubscription.model_validate(w) for w in items]

    def update_webhook(
        self,
        webhook_id: int,
        url: Optional[str] = None,
        events: Optional[list[str]] = None,
        description: Optional[str] = None,
        secret: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> WebhookSubscription:
        """Update a webhook subscription.

        Args:
            webhook_id: The webhook ID.
            url: New webhook URL.
            events: New list of event types.
            description: New description.
            secret: New HMAC secret.
            enabled: New enabled status.
        """
        body: dict[str, Any] = {}
        if url is not None:
            body["url"] = url
        if events is not None:
            body["events"] = events
        if description is not None:
            body["description"] = description
        if secret is not None:
            body["secret"] = secret
        if enabled is not None:
            body["enabled"] = enabled
        resp = self._request("PATCH", f"/api/v1/webhooks/{webhook_id}", json=body)
        return WebhookSubscription.model_validate(resp.json())

    def delete_webhook(self, webhook_id: int) -> dict[str, Any]:
        """Delete a webhook subscription.

        Args:
            webhook_id: The webhook ID.
        """
        resp = self._request("DELETE", f"/api/v1/webhooks/{webhook_id}")
        return resp.json()

    def get_webhook_deliveries(
        self,
        webhook_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WebhookDelivery]:
        """Get delivery history for a webhook.

        Args:
            webhook_id: The webhook ID.
            limit: Maximum number of results.
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        resp = self._request("GET", f"/api/v1/webhooks/{webhook_id}/deliveries", params=params)
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        return [WebhookDelivery.model_validate(d) for d in items]

    def get_webhook_stats(self) -> WebhookStats:
        """Get webhook statistics.

        Returns:
            WebhookStats with aggregate statistics.
        """
        resp = self._request("GET", "/api/v1/webhooks/stats")
        return WebhookStats.model_validate(resp.json())

    # ─── Label History ────────────────────────────────────────────────────

    def get_label_history(
        self,
        resource_id: Optional[str] = None,
        tag_key: Optional[str] = None,
        action: Optional[str] = None,
        tagged_by: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LabelHistoryResult:
        """Get label change history.

        Args:
            resource_id: Filter by resource ID.
            tag_key: Filter by tag key.
            action: Filter by action ('created', 'updated', 'deleted').
            tagged_by: Filter by user who tagged.
            limit: Maximum number of results.
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if resource_id is not None:
            params["resource_id"] = resource_id
        if tag_key is not None:
            params["tag_key"] = tag_key
        if action is not None:
            params["action"] = action
        if tagged_by is not None:
            params["tagged_by"] = tagged_by
        resp = self._request("GET", "/api/v1/labels/history", params=params)
        return LabelHistoryResult.model_validate(resp.json())

    # ─── Patient Sync ─────────────────────────────────────────────────────

    def get_patient_sync_status(self) -> PatientSyncStatus:
        """Get patient sync status between DICOM/BIDS and VNA.

        Returns:
            PatientSyncStatus with sync statistics.
        """
        resp = self._request("GET", "/api/v1/patients/sync-status")
        return PatientSyncStatus.model_validate(resp.json())

    # ─── Batch Resource Operations ───────────────────────────────────────

    def delete_resources(self, resource_ids: list[str]) -> dict[str, Any]:
        """Delete multiple resources.

        Args:
            resource_ids: List of resource IDs to delete.
        """
        resp = self._request("POST", "/api/v1/resources/batch-delete", json={"resource_ids": resource_ids})
        return resp.json()

    def get_resources_by_patient(
        self,
        patient_ref: str,
        limit: int = 50,
        offset: int = 0,
    ) -> QueryResult:
        """Get all resources for a patient.

        Args:
            patient_ref: The patient reference.
            limit: Maximum number of results.
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        resp = self._request("GET", f"/api/v1/patients/{patient_ref}/resources", params=params)
        return QueryResult.model_validate(resp.json())

    # ─── Version Management ───────────────────────────────────────────────

    def create_version(
        self,
        name: str,
        description: Optional[str] = None,
        resource_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new data version snapshot.

        Args:
            name: Version name.
            description: Optional description.
            resource_ids: Optional list of resource IDs to include.
        """
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if resource_ids is not None:
            body["resource_ids"] = resource_ids
        resp = self._request("POST", "/api/v1/versions", json=body)
        return resp.json()

    def list_versions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List all data versions.

        Args:
            limit: Maximum number of results.
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        resp = self._request("GET", "/api/v1/versions", params=params)
        return resp.json()

    def get_version(self, version_id: int) -> dict[str, Any]:
        """Get a specific version by ID.

        Args:
            version_id: The version ID.
        """
        resp = self._request("GET", f"/api/v1/versions/{version_id}")
        return resp.json()

    def compare_versions(
        self,
        version_id_1: int,
        version_id_2: int,
    ) -> dict[str, Any]:
        """Compare two versions.

        Args:
            version_id_1: First version ID.
            version_id_2: Second version ID.
        """
        resp = self._request(
            "GET",
            "/api/v1/versions/compare",
            params={"version_id_1": version_id_1, "version_id_2": version_id_2},
        )
        return resp.json()

    def restore_version(self, version_id: int) -> dict[str, Any]:
        """Restore data to a specific version.

        Args:
            version_id: The version ID to restore.
        """
        resp = self._request("POST", f"/api/v1/versions/{version_id}/restore")
        return resp.json()

    def delete_version(self, version_id: int) -> dict[str, Any]:
        """Delete a version snapshot.

        Args:
            version_id: The version ID.
        """
        resp = self._request("DELETE", f"/api/v1/versions/{version_id}")
        return resp.json()

    # ─── Monitoring ───────────────────────────────────────────────────────

    def get_system_health(self) -> dict[str, Any]:
        """Get comprehensive system health status."""
        resp = self._request("GET", "/api/v1/monitoring/health")
        return resp.json()

    def get_metrics(self) -> dict[str, Any]:
        """Get system metrics."""
        resp = self._request("GET", "/api/v1/monitoring/metrics")
        return resp.json()

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus-formatted metrics."""
        resp = self._request("GET", "/api/v1/monitoring/metrics/prometheus")
        return resp.text

    def get_alerts(
        self,
        active_only: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get system alerts.

        Args:
            active_only: Only return active alerts.
            limit: Maximum number of results.
        """
        params: dict[str, Any] = {"active_only": str(active_only).lower(), "limit": limit}
        resp = self._request("GET", "/api/v1/monitoring/alerts", params=params)
        return resp.json()

    def acknowledge_alert(self, alert_id: int) -> dict[str, Any]:
        """Acknowledge an alert.

        Args:
            alert_id: The alert ID.
        """
        resp = self._request("POST", f"/api/v1/monitoring/alerts/{alert_id}/acknowledge")
        return resp.json()

    def get_component_health(self, component: str) -> dict[str, Any]:
        """Get health status for a specific component.

        Args:
            component: Component name (e.g., 'database', 'redis', 'dicom', 'bids').
        """
        resp = self._request("GET", f"/api/v1/monitoring/health/{component}")
        return resp.json()

    # ─── Routing Rules ────────────────────────────────────────────────────

    def list_routing_rules(
        self,
        enabled_only: bool = False,
        rule_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """List routing rules.

        Args:
            enabled_only: Only return enabled rules.
            rule_type: Filter by rule type.
        """
        params: dict[str, Any] = {}
        if enabled_only:
            params["enabled_only"] = "true"
        if rule_type is not None:
            params["rule_type"] = rule_type
        resp = self._request("GET", "/api/v1/routing/rules", params=params)
        return resp.json()

    def create_routing_rule(
        self,
        name: str,
        target: str,
        rule_type: str = "data_type",
        conditions: Optional[dict[str, Any]] = None,
        description: Optional[str] = None,
        priority: int = 100,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Create a routing rule.

        Args:
            name: Rule name.
            target: Target destination.
            rule_type: Rule type (default: 'data_type').
            conditions: Rule conditions.
            description: Optional description.
            priority: Rule priority (higher = more important).
            enabled: Whether the rule is enabled.
        """
        body: dict[str, Any] = {
            "name": name,
            "target": target,
            "rule_type": rule_type,
            "priority": priority,
            "enabled": enabled,
        }
        if conditions is not None:
            body["conditions"] = conditions
        if description is not None:
            body["description"] = description
        resp = self._request("POST", "/api/v1/routing/rules", json=body)
        return resp.json()

    def get_routing_rule(self, rule_id: int) -> dict[str, Any]:
        """Get a routing rule by ID.

        Args:
            rule_id: The rule ID.
        """
        resp = self._request("GET", f"/api/v1/routing/rules/{rule_id}")
        return resp.json()

    def update_routing_rule(
        self,
        rule_id: int,
        name: Optional[str] = None,
        target: Optional[str] = None,
        rule_type: Optional[str] = None,
        conditions: Optional[dict[str, Any]] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Update a routing rule.

        Args:
            rule_id: The rule ID.
            name: New rule name.
            target: New target destination.
            rule_type: New rule type.
            conditions: New rule conditions.
            description: New description.
            priority: New priority.
            enabled: New enabled status.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if target is not None:
            body["target"] = target
        if rule_type is not None:
            body["rule_type"] = rule_type
        if conditions is not None:
            body["conditions"] = conditions
        if description is not None:
            body["description"] = description
        if priority is not None:
            body["priority"] = priority
        if enabled is not None:
            body["enabled"] = enabled
        resp = self._request("PATCH", f"/api/v1/routing/rules/{rule_id}", json=body)
        return resp.json()

    def delete_routing_rule(self, rule_id: int) -> dict[str, Any]:
        """Delete a routing rule.

        Args:
            rule_id: The rule ID.
        """
        resp = self._request("DELETE", f"/api/v1/routing/rules/{rule_id}")
        return resp.json()

    def evaluate_routing(
        self,
        resource_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate routing rules for a resource.

        Args:
            resource_data: Resource data to evaluate.
        """
        resp = self._request("POST", "/api/v1/routing/evaluate", json=resource_data)
        return resp.json()

    def test_routing_rule(
        self,
        conditions: dict[str, Any],
        test_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Test a routing rule against sample data.

        Args:
            conditions: Rule conditions to test.
            test_data: Sample data to test against.
        """
        resp = self._request(
            "POST",
            "/api/v1/routing/test",
            json={"conditions": conditions, "test_data": test_data},
        )
        return resp.json()
