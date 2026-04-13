"""Integration tests for VNA Main SDK - client-to-server communication."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from vna_main_sdk import VnaClient, AsyncVnaClient
from vna_main_sdk.client import VnaClientError
from vna_main_sdk.models import (
    DataType,
    Label,
    Patient,
    Resource,
    SourceType,
    SyncStatus,
    WebhookSubscription,
)


def make_mock_response(
    status_code: int = 200,
    json_data: Any = None,
    content: bytes = b"",
) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if 200 <= status_code < 300:
        resp.raise_for_status = MagicMock()
    else:
        def raise_for_status():
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=resp,
            )
        resp.raise_for_status = raise_for_status
    resp.text = str(json_data) if json_data else ""
    return resp


@pytest.fixture
def sync_client():
    client = VnaClient(base_url="http://localhost:8000", api_key="test-key")
    yield client
    client.close()


class TestVnaClientInit:
    def test_base_url_strips_trailing_slash(self):
        c = VnaClient("http://localhost:8000/")
        assert c.base_url == "http://localhost:8000"
        c.close()

    def test_context_manager(self):
        with VnaClient("http://localhost:8000") as c:
            assert c.base_url == "http://localhost:8000"

    def test_api_key_header(self):
        c = VnaClient("http://localhost:8000", api_key="my-key")
        assert c._headers["Authorization"] == "Bearer my-key"
        c.close()


class TestResourcesAPI:
    def test_register_resource(self, sync_client):
        mock_resp = make_mock_response(201, {
            "resource_id": "res-001",
            "patient_ref": "pt-001",
            "source_type": "dicom",
            "data_type": "imaging",
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            resource = sync_client.register_resource(
                patient_ref="pt-001",
                source_type=SourceType.DICOM,
                dicom_study_uid="1.2.3.4",
            )
            assert resource.resource_id == "res-001"
            assert resource.source_type == SourceType.DICOM

    def test_list_resources(self, sync_client):
        mock_resp = make_mock_response(200, {
            "total": 1,
            "limit": 50,
            "offset": 0,
            "resources": [{
                "resource_id": "res-001",
                "patient_ref": "pt-001",
                "source_type": "dicom",
                "data_type": "imaging",
            }],
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.list_resources(limit=10)
            assert result.total == 1
            assert len(result.resources) == 1

    def test_get_resource(self, sync_client):
        mock_resp = make_mock_response(200, {
            "resource_id": "res-get",
            "patient_ref": "pt-001",
            "source_type": "bids",
            "data_type": "imaging",
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            resource = sync_client.get_resource("res-get")
            assert resource.resource_id == "res-get"
            assert resource.source_type == SourceType.BIDS

    def test_delete_resource(self, sync_client):
        mock_resp = make_mock_response(200, {"deleted": True})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.delete_resource("res-001")
            assert result["deleted"] is True

    def test_delete_resources_batch(self, sync_client):
        mock_resp = make_mock_response(200, {"deleted": 3, "resource_ids": ["r1", "r2", "r3"]})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.delete_resources(["r1", "r2", "r3"])
            assert result["deleted"] == 3


class TestPatientsAPI:
    def test_create_patient(self, sync_client):
        mock_resp = make_mock_response(201, {
            "patient_ref": "pt-new",
            "hospital_id": "H001",
            "source": "hospitalA",
            "resource_count": 0,
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            patient = sync_client.create_patient(
                patient_ref="pt-new",
                hospital_id="H001",
                source="hospitalA",
            )
            assert patient.patient_ref == "pt-new"
            assert patient.hospital_id == "H001"

    def test_get_patient(self, sync_client):
        mock_resp = make_mock_response(200, {
            "patient_ref": "pt-get",
            "hospital_id": "H002",
            "source": "hospitalB",
            "resource_count": 5,
            "resources": [],
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            patient = sync_client.get_patient("pt-get")
            assert patient.patient_ref == "pt-get"
            assert patient.resource_count == 5

    def test_get_resources_by_patient(self, sync_client):
        mock_resp = make_mock_response(200, {
            "total": 2,
            "resources": [
                {"resource_id": "res-1", "patient_ref": "pt-001", "source_type": "dicom", "data_type": "imaging"},
                {"resource_id": "res-2", "patient_ref": "pt-001", "source_type": "bids", "data_type": "imaging"},
            ],
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.get_resources_by_patient("pt-001")
            assert result.total == 2


class TestLabelsAPI:
    def test_set_labels(self, sync_client):
        mock_resp = make_mock_response(200, [
            {"key": "modality", "value": "CT"},
            {"key": "project", "value": "lung-cancer"},
        ])
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            labels = sync_client.set_labels("res-001", {"modality": "CT", "project": "lung-cancer"})
            assert len(labels) == 2

    def test_patch_labels(self, sync_client):
        mock_resp = make_mock_response(200, [
            {"key": "modality", "value": "MR"},
        ])
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            labels = sync_client.patch_labels(
                "res-001",
                add={"modality": "MR"},
                remove=["status"],
            )
            assert labels[0].value == "MR"

    def test_get_label_history(self, sync_client):
        mock_resp = make_mock_response(200, {
            "total": 2,
            "items": [
                {"id": 1, "resource_id": "res-001", "tag_key": "status", "tag_value": "pending", "tag_type": "custom", "action": "created"},
                {"id": 2, "resource_id": "res-001", "tag_key": "status", "tag_value": "pending", "tag_type": "custom", "action": "deleted"},
            ],
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.get_label_history(resource_id="res-001")
            assert result.total == 2
            actions = {item.action for item in result.items}
            assert "created" in actions
            assert "deleted" in actions


class TestQueryAPI:
    def test_query_unified(self, sync_client):
        mock_resp = make_mock_response(200, {
            "total": 1,
            "resources": [{
                "resource_id": "res-q",
                "patient_ref": "pt-q",
                "source_type": "dicom",
                "data_type": "imaging",
            }],
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.query(source_type=SourceType.DICOM, limit=10)
            assert result.total == 1


class TestWebhookAPI:
    def test_create_webhook(self, sync_client):
        mock_resp = make_mock_response(200, {
            "id": 1,
            "url": "https://example.com/hook",
            "events": ["resource.created"],
            "secret": "abc123",
            "enabled": True,
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            wh = sync_client.create_webhook(
                url="https://example.com/hook",
                events=["resource.created"],
            )
            assert wh.id == 1
            assert wh.url == "https://example.com/hook"
            assert wh.enabled is True

    def test_get_webhook(self, sync_client):
        mock_resp = make_mock_response(200, {
            "id": 42,
            "url": "https://example.com/get",
            "events": ["resource.deleted"],
            "enabled": False,
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            wh = sync_client.get_webhook(42)
            assert wh.id == 42
            assert wh.enabled is False

    def test_list_webhooks(self, sync_client):
        mock_resp = make_mock_response(200, {
            "items": [
                {"id": 1, "url": "https://example.com/1", "events": ["a"], "enabled": True},
                {"id": 2, "url": "https://example.com/2", "events": ["b"], "enabled": False},
            ]
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            webhooks = sync_client.list_webhooks()
            assert len(webhooks) == 2

    def test_update_webhook(self, sync_client):
        mock_resp = make_mock_response(200, {
            "id": 1,
            "url": "https://example.com/updated",
            "events": ["resource.updated"],
            "enabled": False,
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            wh = sync_client.update_webhook(
                webhook_id=1,
                events=["resource.updated"],
                enabled=False,
            )
            assert wh.enabled is False
            assert "updated" in wh.url

    def test_delete_webhook(self, sync_client):
        mock_resp = make_mock_response(200, {"deleted": True})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.delete_webhook(1)
            assert result["deleted"] is True

    def test_get_webhook_stats(self, sync_client):
        mock_resp = make_mock_response(200, {
            "total": 3,
            "enabled": 2,
            "disabled": 1,
            "event_counts": {"resource.created": 5, "resource.deleted": 2},
            "total_deliveries": 10,
            "successful_deliveries": 8,
            "failed_deliveries": 2,
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            stats = sync_client.get_webhook_stats()
            assert stats.total == 3
            assert stats.enabled == 2
            assert stats.successful_deliveries == 8

    def test_get_webhook_deliveries(self, sync_client):
        mock_resp = make_mock_response(200, {
            "items": [
                {"delivery_id": "d1", "webhook_id": 1, "event": "resource.created", "status_code": 200},
                {"delivery_id": "d2", "webhook_id": 1, "event": "resource.created", "status_code": 500},
            ],
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            deliveries = sync_client.get_webhook_deliveries(webhook_id=1)
            assert len(deliveries) == 2


class TestSyncAPI:
    def test_sync_status(self, sync_client):
        mock_resp = make_mock_response(200, {
            "dicom": {"status": "ok", "last_sync": "2024-01-01T00:00:00Z"},
            "bids": {"status": "ok", "last_sync": "2024-01-01T00:00:00Z"},
            "events": [],
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            status = sync_client.sync_status()
            assert "dicom" in status.dicom

    def test_trigger_sync(self, sync_client):
        mock_resp = make_mock_response(200, {
            "dicom": {"status": "ok", "last_sync": "2024-01-02T00:00:00Z"},
            "bids": {"status": "ok", "last_sync": "2024-01-02T00:00:00Z"},
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            status = sync_client.trigger_sync(SourceType.DICOM)
            assert status is not None


class TestPatientSyncAPI:
    def test_get_patient_sync_status(self, sync_client):
        mock_resp = make_mock_response(200, {
            "total_patients": 100,
            "dicom_patients": 60,
            "bids_patients": 40,
            "total_resources": 500,
            "mapped_resources": 480,
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            status = sync_client.get_patient_sync_status()
            assert status.total_patients == 100
            assert status.dicom_patients == 60
            assert status.mapped_resources == 480


class TestExceptions:
    def test_http_error_raises(self, sync_client):
        mock_resp = make_mock_response(404, {"detail": "Not found"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            with pytest.raises(VnaClientError) as exc_info:
                sync_client.get_resource("nonexistent")
            assert exc_info.value.status_code == 404

    def test_connection_error_raises(self, sync_client):
        with patch.object(sync_client._client, "request", side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(VnaClientError, match="Request failed"):
                sync_client.list_resources()
