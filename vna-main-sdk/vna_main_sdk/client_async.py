"""Asynchronous VNA Main Server client."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from vna_main_sdk.client import VnaClient, VnaClientError
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


class AsyncVnaClient:
    """Asynchronous client for the VNA Main Server.

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
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=timeout,
            verify=verify_ssl,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncVnaClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        """Make an async HTTP request and handle errors."""
        try:
            resp = await self._client.request(method, path, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            detail = None
            try:
                detail = e.response.json()
            except (json.JSONDecodeError, ValueError):
                detail = e.response.text
            message = VnaClient._extract_error_message(e.response.reason_phrase, detail)
            raise VnaClientError(
                f"HTTP {e.response.status_code}: {message}",
                status_code=e.response.status_code,
                detail=detail,
            ) from e
        except httpx.RequestError as e:
            raise VnaClientError(f"Request failed: {e}") from e

    # ─── Resources ─────────────────────────────────────────────────────────

    async def list_resources(
        self,
        patient_ref: Optional[str] = None,
        data_type: Optional[str | DataType] = None,
        source_type: Optional[str | SourceType] = None,
        labels: Optional[dict[str, Optional[str]]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> QueryResult:
        """List resources with optional filters."""
        if labels:
            return await self.query(
                patient_ref=patient_ref,
                data_type=data_type,
                source_type=source_type,
                labels=labels,
                limit=limit,
                offset=offset,
            )
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if patient_ref is not None:
            params["patient_ref"] = patient_ref
        if data_type is not None:
            params["data_type"] = VnaClient._enum_value(data_type)
        if source_type is not None:
            params["source_type"] = VnaClient._enum_value(source_type)
        resp = await self._request("GET", "/api/v1/resources", params=params)
        return QueryResult.model_validate(resp.json())

    async def get_resource(self, resource_id: str) -> Resource:
        """Get a resource by ID with merged DICOM+BIDS view."""
        resp = await self._request("GET", f"/api/v1/resources/{resource_id}")
        return Resource.model_validate(resp.json())

    async def register_resource(
        self,
        patient_ref: str,
        source_type: str | SourceType,
        dicom_study_uid: Optional[str] = None,
        dicom_series_uid: Optional[str] = None,
        dicom_sop_uid: Optional[str] = None,
        bids_path: Optional[str] = None,
        bids_subject: Optional[str] = None,
        bids_session: Optional[str] = None,
        bids_datatype: Optional[str] = None,
        data_type: Optional[str | DataType] = None,
        labels: Optional[dict[str, Optional[str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Resource:
        """Register a new resource."""
        body = VnaClient._resource_body(
            patient_ref=patient_ref,
            source_type=source_type,
            dicom_study_uid=dicom_study_uid,
            dicom_series_uid=dicom_series_uid,
            dicom_sop_uid=dicom_sop_uid,
            bids_path=bids_path,
            bids_subject=bids_subject,
            bids_session=bids_session,
            data_type=data_type,
            metadata=metadata,
        )
        if bids_datatype is not None:
            body.setdefault("metadata", {})["bids_datatype"] = bids_datatype
        resp = await self._request("POST", "/api/v1/resources", json=body)
        resource = Resource.model_validate(resp.json())
        if labels:
            await self.set_labels(resource.resource_id, labels)
            return await self.get_resource(resource.resource_id)
        return resource

    async def update_resource(
        self,
        resource_id: str,
        patient_ref: Optional[str] = None,
        source_type: Optional[str | SourceType] = None,
        dicom_study_uid: Optional[str] = None,
        dicom_series_uid: Optional[str] = None,
        dicom_sop_uid: Optional[str] = None,
        bids_path: Optional[str] = None,
        bids_subject: Optional[str] = None,
        bids_session: Optional[str] = None,
        bids_datatype: Optional[str] = None,
        data_type: Optional[str | DataType] = None,
        labels: Optional[dict[str, Optional[str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Resource:
        """Update an existing resource."""
        body = VnaClient._resource_body(
            patient_ref=patient_ref,
            source_type=source_type,
            dicom_study_uid=dicom_study_uid,
            dicom_series_uid=dicom_series_uid,
            dicom_sop_uid=dicom_sop_uid,
            bids_path=bids_path,
            bids_subject=bids_subject,
            bids_session=bids_session,
            data_type=data_type,
            metadata=metadata,
        )
        if bids_datatype is not None:
            body.setdefault("metadata", {})["bids_datatype"] = bids_datatype
        resp = await self._request("PATCH", f"/api/v1/resources/{resource_id}", json=body)
        resource = Resource.model_validate(resp.json())
        if labels is not None:
            await self.set_labels(resource_id, labels)
            return await self.get_resource(resource_id)
        return resource

    async def delete_resource(self, resource_id: str) -> dict[str, Any]:
        """Delete a resource from the index."""
        resp = await self._request("DELETE", f"/api/v1/resources/{resource_id}")
        return resp.json()

    # ─── Patients ──────────────────────────────────────────────────────────

    async def get_patient(self, patient_ref: str) -> Patient:
        """Get a patient with all resources."""
        resp = await self._request("GET", f"/api/v1/patients/{patient_ref}")
        return Patient.model_validate(resp.json())

    async def list_patients(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List patients."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        resp = await self._request("GET", "/api/v1/patients", params=params)
        return resp.json()

    async def create_patient(
        self,
        patient_ref: str,
        hospital_id: str,
        source: str,
        external_system: Optional[str] = None,
    ) -> Patient:
        """Create a patient ID mapping."""
        body: dict[str, Any] = {
            "patient_ref": patient_ref,
            "hospital_id": hospital_id,
            "source": source,
        }
        if external_system is not None:
            body["external_system"] = external_system
        resp = await self._request("POST", "/api/v1/patients", json=body)
        return Patient.model_validate(resp.json())

    async def update_patient(
        self,
        patient_ref: str,
        hospital_id: Optional[str] = None,
        source: Optional[str] = None,
        external_system: Optional[str] = None,
    ) -> Patient:
        """Update a patient mapping."""
        body: dict[str, Any] = {}
        if hospital_id is not None:
            body["hospital_id"] = hospital_id
        if source is not None:
            body["source"] = source
        if external_system is not None:
            body["external_system"] = external_system
        resp = await self._request("PUT", f"/api/v1/patients/{patient_ref}", json=body)
        return Patient.model_validate(resp.json())

    # ─── Labels ────────────────────────────────────────────────────────────

    async def get_labels(self, resource_id: str) -> list[Label]:
        """Get labels for a resource."""
        resp = await self._request("GET", f"/api/v1/labels/resource/{resource_id}")
        return VnaClient._parse_labels(resp.json())

    async def set_labels(
        self, resource_id: str, labels: dict[str, Optional[str]]
    ) -> list[Label]:
        """Set labels for a resource (replaces existing)."""
        resp = await self._request(
            "PUT",
            f"/api/v1/labels/resource/{resource_id}",
            json={"labels": VnaClient._label_items(labels)},
        )
        return VnaClient._parse_labels(resp.json())

    async def patch_labels(
        self,
        resource_id: str,
        add: Optional[dict[str, Optional[str]]] = None,
        remove: Optional[list[str]] = None,
    ) -> list[Label]:
        """Patch labels for a resource (add/remove)."""
        if remove:
            current = {label.key: label.value for label in await self.get_labels(resource_id)}
            current.update(add or {})
            for key in remove:
                current.pop(key, None)
            return await self.set_labels(resource_id, current)
        resp = await self._request(
            "PATCH",
            f"/api/v1/labels/resource/{resource_id}",
            json={"labels": VnaClient._label_items(add)},
        )
        return VnaClient._parse_labels(resp.json())

    async def list_all_tags(self) -> list[TagInfo]:
        """List all tags with counts."""
        resp = await self._request("GET", "/api/v1/labels")
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        counts: dict[tuple[str, Optional[str]], int] = {}
        for item in items:
            key = item.get("tag_key")
            value = item.get("tag_value")
            counts[(key, value)] = counts.get((key, value), 0) + 1
        return [
            TagInfo.model_validate({"tag_key": key, "tag_value": value, "count": count})
            for (key, value), count in sorted(counts.items())
        ]

    async def batch_label(self, operations: list[BatchLabelOperation]) -> dict[str, Any]:
        """Execute batch label operations."""
        resp = await self._request(
            "POST",
            "/api/v1/labels/batch",
            json={"operations": [VnaClient._serialize_batch_operation(self, op) for op in operations]},
        )
        return resp.json()

    # ─── Query ─────────────────────────────────────────────────────────────

    async def query(
        self,
        patient_ref: Optional[str] = None,
        data_type: Optional[str | DataType] = None,
        source_type: Optional[str | SourceType] = None,
        labels: Optional[dict[str, Optional[str]]] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> QueryResult:
        """Unified query across all data sources."""
        body: dict[str, Any] = {"limit": limit, "offset": offset}
        if patient_ref is not None:
            body["patient_ref"] = patient_ref
        if data_type is not None:
            body["data_type"] = VnaClient._enum_value(data_type)
        if source_type is not None:
            body["source_type"] = VnaClient._enum_value(source_type)
        if labels:
            body["labels"] = VnaClient._label_items(labels)
        if search is not None:
            body["text_search"] = search
        resp = await self._request("POST", "/api/v1/query", json=body)
        return QueryResult.model_validate(resp.json())

    # ─── Server Management ─────────────────────────────────────────────────

    async def register_server(
        self,
        server_type: str,
        url: str,
        name: Optional[str] = None,
    ) -> ServerRegistration:
        """Register a DICOM or BIDS server."""
        body = {"source_db": server_type, "url": url}
        resp = await self._request("POST", "/api/v1/sync/register", json=body)
        return ServerRegistration.model_validate(resp.json())

    # ─── Sync ──────────────────────────────────────────────────────────────

    async def sync_status(self) -> SyncStatus:
        """Get sync status."""
        resp = await self._request("GET", "/api/v1/sync/status")
        return SyncStatus.model_validate(resp.json())

    async def trigger_sync(self, source: Optional[str | SourceType] = None) -> SyncStatus:
        """Trigger manual sync."""
        params: dict[str, Any] = {}
        if source is not None:
            params["source_db"] = VnaClient._enum_value(source)
        resp = await self._request("POST", "/api/v1/sync/trigger", params=params)
        return SyncStatus.model_validate(resp.json())

    # ─── Health ────────────────────────────────────────────────────────────

    async def health(self) -> HealthStatus:
        """Health check."""
        resp = await self._request("GET", "/api/v1/health")
        return HealthStatus.model_validate(resp.json())

    # ─── Webhooks ─────────────────────────────────────────────────────────

    async def create_webhook(
        self,
        url: str,
        events: list[str],
        description: Optional[str] = None,
        secret: Optional[str] = None,
        enabled: bool = True,
    ) -> WebhookSubscription:
        """Create a webhook subscription."""
        body: dict[str, Any] = {"url": url, "events": events}
        if description is not None:
            body["description"] = description
        if secret is not None:
            body["secret"] = secret
        body["enabled"] = enabled
        resp = await self._request("POST", "/api/v1/webhooks", json=body)
        return WebhookSubscription.model_validate(resp.json())

    async def get_webhook(self, webhook_id: int) -> WebhookSubscription:
        """Get a webhook subscription by ID."""
        resp = await self._request("GET", f"/api/v1/webhooks/{webhook_id}")
        return WebhookSubscription.model_validate(resp.json())

    async def list_webhooks(
        self,
        event: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> list[WebhookSubscription]:
        """List webhook subscriptions."""
        params: dict[str, Any] = {}
        if event is not None:
            params["event"] = event
        if enabled is not None:
            params["enabled"] = str(enabled).lower()
        resp = await self._request("GET", "/api/v1/webhooks", params=params)
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        return [WebhookSubscription.model_validate(w) for w in items]

    async def update_webhook(
        self,
        webhook_id: int,
        url: Optional[str] = None,
        events: Optional[list[str]] = None,
        description: Optional[str] = None,
        secret: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> WebhookSubscription:
        """Update a webhook subscription."""
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
        resp = await self._request("PATCH", f"/api/v1/webhooks/{webhook_id}", json=body)
        return WebhookSubscription.model_validate(resp.json())

    async def delete_webhook(self, webhook_id: int) -> dict[str, Any]:
        """Delete a webhook subscription."""
        resp = await self._request("DELETE", f"/api/v1/webhooks/{webhook_id}")
        return resp.json()

    async def get_webhook_deliveries(
        self,
        webhook_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WebhookDelivery]:
        """Get delivery history for a webhook."""
        params: dict[str, Any] = {"limit": limit}
        resp = await self._request("GET", f"/api/v1/webhooks/{webhook_id}/deliveries", params=params)
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        return [WebhookDelivery.model_validate(d) for d in items]

    async def get_webhook_stats(self) -> WebhookStats:
        """Get webhook statistics."""
        resp = await self._request("GET", "/api/v1/webhooks/stats")
        return WebhookStats.model_validate(resp.json())

    # ─── Label History ────────────────────────────────────────────────────

    async def get_label_history(
        self,
        resource_id: Optional[str] = None,
        tag_key: Optional[str] = None,
        action: Optional[str] = None,
        tagged_by: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LabelHistoryResult:
        """Get label change history."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if resource_id is not None:
            params["resource_id"] = resource_id
        if tag_key is not None:
            params["tag_key"] = tag_key
        if action is not None:
            params["action"] = action
        if tagged_by is not None:
            params["tagged_by"] = tagged_by
        resp = await self._request("GET", "/api/v1/labels/history", params=params)
        return LabelHistoryResult.model_validate(resp.json())

    # ─── Patient Sync ─────────────────────────────────────────────────────

    async def get_patient_sync_status(self) -> PatientSyncStatus:
        """Get patient sync status between DICOM/BIDS and VNA."""
        resp = await self._request("GET", "/api/v1/patients/sync-status")
        return PatientSyncStatus.model_validate(resp.json())

    # ─── Batch Resource Operations ───────────────────────────────────────

    async def delete_resources(self, resource_ids: list[str]) -> dict[str, Any]:
        """Delete multiple resources."""
        deleted: list[Any] = []
        failed: dict[str, Any] = {}
        for resource_id in resource_ids:
            try:
                deleted.append((await self.delete_resource(resource_id)).get("deleted", resource_id))
            except VnaClientError as exc:
                failed[resource_id] = exc.detail or str(exc)
        return {"deleted": deleted, "failed": failed, "total": len(resource_ids)}

    async def get_resources_by_patient(
        self,
        patient_ref: str,
        limit: int = 50,
        offset: int = 0,
    ) -> QueryResult:
        """Get all resources for a patient."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        resp = await self._request("GET", f"/api/v1/patients/{patient_ref}/resources", params=params)
        return QueryResult.model_validate(resp.json())

    # ─── Version Management ───────────────────────────────────────────────

    async def create_version(
        self,
        name: str,
        description: Optional[str] = None,
        resource_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new data version snapshot."""
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        if resource_ids is not None:
            body["filters"] = {"resource_ids": resource_ids}
        resp = await self._request("POST", "/api/v1/versions/snapshots", json=body)
        return resp.json()

    async def list_versions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List all data versions."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        resp = await self._request("GET", "/api/v1/versions/snapshots", params=params)
        return resp.json()

    async def get_version(self, version_id: int | str) -> dict[str, Any]:
        """Get a specific version by ID."""
        resp = await self._request("GET", f"/api/v1/versions/snapshots/{version_id}")
        return resp.json()

    async def compare_versions(
        self,
        version_id_1: int,
        version_id_2: int,
        resource_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Compare two versions."""
        if resource_id is None:
            raise VnaClientError("Version comparison is resource-scoped; pass resource_id.")
        resp = await self._request(
            "GET",
            f"/api/v1/versions/resources/{resource_id}/versions/{version_id_1}/compare/{version_id_2}",
        )
        return resp.json()

    async def restore_version(
        self,
        version_id: int,
        *,
        resource_id: Optional[str] = None,
        restored_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """Restore data to a specific version."""
        if resource_id is None:
            raise VnaClientError("Version restore is resource-scoped; pass resource_id.")
        params: dict[str, Any] = {}
        if restored_by is not None:
            params["restored_by"] = restored_by
        resp = await self._request(
            "POST",
            f"/api/v1/versions/resources/{resource_id}/versions/{version_id}/restore",
            params=params,
        )
        return resp.json()

    async def delete_version(self, version_id: int | str) -> dict[str, Any]:
        """Delete a version snapshot."""
        resp = await self._request("DELETE", f"/api/v1/versions/snapshots/{version_id}")
        return resp.json()

    # ─── Monitoring ───────────────────────────────────────────────────────

    async def get_system_health(self) -> dict[str, Any]:
        """Get comprehensive system health status."""
        resp = await self._request("GET", "/api/v1/monitoring/health")
        return resp.json()

    async def get_metrics(self) -> dict[str, Any]:
        """Get system metrics."""
        resp = await self._request("GET", "/api/v1/monitoring/metrics")
        return resp.json()

    async def get_prometheus_metrics(self) -> str:
        """Get Prometheus-formatted metrics."""
        resp = await self._request("GET", "/api/v1/monitoring/metrics/prometheus")
        return resp.text

    async def get_alerts(
        self,
        active_only: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get system alerts."""
        resp = await self._request("GET", "/api/v1/monitoring/alerts")
        return resp.json()

    async def acknowledge_alert(self, alert_id: int) -> dict[str, Any]:
        """Acknowledge an alert."""
        raise VnaClientError("Alert acknowledgement is not supported by the current server API.")

    async def get_component_health(self, component: str) -> dict[str, Any]:
        """Get health status for a specific component."""
        resp = await self._request("GET", f"/api/v1/monitoring/health/{component}")
        return resp.json()

    # ─── Routing Rules ────────────────────────────────────────────────────

    async def list_routing_rules(
        self,
        enabled_only: bool = False,
        rule_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """List routing rules."""
        params: dict[str, Any] = {}
        if enabled_only:
            params["enabled_only"] = "true"
        if rule_type is not None:
            params["rule_type"] = rule_type
        resp = await self._request("GET", "/api/v1/routing/rules", params=params)
        return resp.json()

    async def create_routing_rule(
        self,
        name: str,
        target: str,
        rule_type: str = "data_type",
        conditions: Optional[dict[str, Any]] = None,
        description: Optional[str] = None,
        priority: int = 100,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Create a routing rule."""
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
        resp = await self._request("POST", "/api/v1/routing/rules", json=body)
        return resp.json()

    async def get_routing_rule(self, rule_id: int) -> dict[str, Any]:
        """Get a routing rule by ID."""
        resp = await self._request("GET", f"/api/v1/routing/rules/{rule_id}")
        return resp.json()

    async def update_routing_rule(
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
        """Update a routing rule."""
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
        resp = await self._request("PUT", f"/api/v1/routing/rules/{rule_id}", json=body)
        return resp.json()

    async def delete_routing_rule(self, rule_id: int) -> dict[str, Any]:
        """Delete a routing rule."""
        resp = await self._request("DELETE", f"/api/v1/routing/rules/{rule_id}")
        return resp.json()

    async def evaluate_routing(
        self,
        resource_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate routing rules for a resource."""
        resp = await self._request("POST", "/api/v1/routing/evaluate", json=resource_data)
        return resp.json()

    async def test_routing_rule(
        self,
        conditions: dict[str, Any],
        test_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Test a routing rule against sample data."""
        resp = await self._request(
            "POST",
            "/api/v1/routing/test",
            json={"conditions": conditions, "resource_data": test_data},
        )
        return resp.json()
