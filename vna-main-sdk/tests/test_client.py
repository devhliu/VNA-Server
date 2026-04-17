"""Unit tests for VnaClient with respx mocking."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import respx
import httpx
from httpx import Response

from vna_main_sdk.client import VnaClient, VnaClientError
from vna_main_sdk.models import BatchLabelOperation, DataType, SourceType


BASE_URL = "http://test.vna.local"


@pytest.fixture
def client() -> VnaClient:
    """Create a test client."""
    c = VnaClient(base_url=BASE_URL)
    yield c
    c.close()


# ─── Health ────────────────────────────────────────────────────────────────────

@respx.mock
def test_health(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/health").mock(
        return_value=Response(200, json={"status": "ok", "version": "1.0.0", "database": "ok", "uptime_seconds": 123.4, "timestamp": "2026-01-01T00:00:00Z"})
    )
    result = client.health()
    assert result.status == "ok"
    assert result.version == "1.0.0"
    assert result.database == "ok"


@respx.mock
def test_health_error(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/health").mock(return_value=Response(500, text="Internal error"))
    with pytest.raises(VnaClientError) as exc:
        client.health()
    assert exc.value.status_code == 500


# ─── Resources ─────────────────────────────────────────────────────────────────

@respx.mock
def test_list_resources(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/resources").mock(
        return_value=Response(200, json={
            "total": 1, "limit": 50, "offset": 0,
            "resources": [{"resource_id": "r1", "patient_ref": "p1", "source_type": "dicom", "data_type": "imaging", "labels": [], "metadata": {}, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}]
        })
    )
    result = client.list_resources()
    assert result.total == 1
    assert result.resources[0].resource_id == "r1"


@respx.mock
def test_list_resources_with_filters(client: VnaClient) -> None:
    route = respx.get(f"{BASE_URL}/api/v1/resources").mock(
        return_value=Response(200, json={"total": 0, "limit": 10, "offset": 0, "resources": []})
    )
    result = client.list_resources(patient_ref="p1", data_type="imaging", source_type="dicom", limit=10, offset=5)
    assert result.total == 0
    call = route.calls[0]
    assert "patient_ref=p1" in str(call.request.url)


@respx.mock
def test_list_resources_with_labels(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/query").mock(
        return_value=Response(200, json={"total": 0, "limit": 50, "offset": 0, "items": []})
    )
    result = client.list_resources(labels={"modality": "MRI"})
    assert result.total == 0


@respx.mock
def test_get_resource(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/resources/res-123").mock(
        return_value=Response(200, json={"resource_id": "res-123", "patient_ref": "p1", "source_type": "dicom", "data_type": "imaging", "labels": [], "metadata": {}, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"})
    )
    result = client.get_resource("res-123")
    assert result.resource_id == "res-123"
    assert result.patient_ref == "p1"


@respx.mock
def test_get_resource_not_found(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/resources/nope").mock(return_value=Response(404, json={"detail": "Not found"}))
    with pytest.raises(VnaClientError) as exc:
        client.get_resource("nope")
    assert exc.value.status_code == 404


@respx.mock
def test_register_resource(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/resources").mock(
        return_value=Response(201, json={"resource_id": "new-1", "patient_ref": "p1", "source_type": "dicom", "data_type": "imaging", "labels": [], "metadata": {}, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"})
    )
    result = client.register_resource(patient_ref="p1", source_type="dicom", dicom_study_uid="1.2.3.4")
    assert result.resource_id == "new-1"


@respx.mock
def test_register_resource_bids(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/resources").mock(
        return_value=Response(201, json={"resource_id": "bids-1", "patient_ref": "p2", "source_type": "bids", "data_type": "bids_raw", "bids_path": "/data/sub-01", "labels": [], "metadata": {}, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"})
    )
    result = client.register_resource(patient_ref="p2", source_type=SourceType.BIDS, bids_path="/data/sub-01", bids_subject="sub-01", bids_datatype="anat")
    assert result.resource_id == "bids-1"


@respx.mock
def test_update_resource(client: VnaClient) -> None:
    respx.patch(f"{BASE_URL}/api/v1/resources/res-1").mock(
        return_value=Response(200, json={"resource_id": "res-1", "patient_ref": "p-updated", "source_type": "dicom", "data_type": "imaging", "labels": [], "metadata": {}, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z"})
    )
    result = client.update_resource("res-1", patient_ref="p-updated")
    assert result.patient_ref == "p-updated"


@respx.mock
def test_delete_resource(client: VnaClient) -> None:
    respx.delete(f"{BASE_URL}/api/v1/resources/res-1").mock(
        return_value=Response(200, json={"deleted": True})
    )
    result = client.delete_resource("res-1")
    assert result["deleted"] is True


# ─── Patients ──────────────────────────────────────────────────────────────────

@respx.mock
def test_get_patient(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/patients/p1").mock(
        return_value=Response(200, json={"patient_ref": "p1", "hospital_id": "H123", "source": "hospital_a", "resource_count": 5, "resources": [], "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"})
    )
    result = client.get_patient("p1")
    assert result.patient_ref == "p1"
    assert result.hospital_id == "H123"


@respx.mock
def test_list_patients(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/patients").mock(
        return_value=Response(200, json={"total": 2, "patients": [{"patient_ref": "p1"}, {"patient_ref": "p2"}]})
    )
    result = client.list_patients()
    assert result["total"] == 2


@respx.mock
def test_create_patient(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/patients").mock(
        return_value=Response(201, json={"patient_ref": "p-new", "hospital_id": "H456", "source": "hospital_b", "resource_count": 0, "resources": [], "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"})
    )
    result = client.create_patient("p-new", hospital_id="H456", source="hospital_b")
    assert result.patient_ref == "p-new"
    assert result.hospital_id == "H456"


@respx.mock
def test_update_patient(client: VnaClient) -> None:
    respx.put(f"{BASE_URL}/api/v1/patients/p1").mock(
        return_value=Response(200, json={"patient_ref": "p1", "hospital_id": "H999", "source": "hospital_c", "resource_count": 3, "resources": [], "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z"})
    )
    result = client.update_patient("p1", hospital_id="H999")
    assert result.hospital_id == "H999"


# ─── Labels ────────────────────────────────────────────────────────────────────

@respx.mock
def test_get_labels(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/labels/resource/r1").mock(
        return_value=Response(200, json={"labels": [{"tag_key": "modality", "tag_value": "MRI"}, {"tag_key": "site", "tag_value": "A"}]})
    )
    result = client.get_labels("r1")
    assert len(result) == 2
    assert result[0].key == "modality"


@respx.mock
def test_get_labels_dict_response(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/labels/resource/r1").mock(
        return_value=Response(200, json={"labels": [{"tag_key": "k1", "tag_value": "v1"}]})
    )
    result = client.get_labels("r1")
    assert len(result) == 1


@respx.mock
def test_set_labels(client: VnaClient) -> None:
    route = respx.put(f"{BASE_URL}/api/v1/labels/resource/r1").mock(
        return_value=Response(200, json={"labels": [{"tag_key": "modality", "tag_value": "CT"}]})
    )
    result = client.set_labels("r1", {"modality": "CT"})
    assert result[0].value == "CT"
    assert json.loads(route.calls[0].request.content) == {
        "labels": [{"tag_key": "modality", "tag_value": "CT"}]
    }


@respx.mock
def test_set_labels_dict_response(client: VnaClient) -> None:
    respx.put(f"{BASE_URL}/api/v1/labels/resource/r1").mock(
        return_value=Response(200, json={"labels": [{"tag_key": "new", "tag_value": "val"}]})
    )
    result = client.set_labels("r1", {"new": "val"})
    assert result[0].key == "new"


@respx.mock
def test_patch_labels(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/labels/resource/r1").mock(
        return_value=Response(200, json={"labels": [{"tag_key": "old_key", "tag_value": "old"}]})
    )
    respx.put(f"{BASE_URL}/api/v1/labels/resource/r1").mock(
        return_value=Response(200, json={"labels": [{"tag_key": "k1", "tag_value": "v1"}, {"tag_key": "k2", "tag_value": "v2"}]})
    )
    result = client.patch_labels("r1", add={"k1": "v1", "k2": "v2"}, remove=["old_key"])
    assert len(result) == 2


@respx.mock
def test_patch_labels_add_only(client: VnaClient) -> None:
    respx.patch(f"{BASE_URL}/api/v1/labels/resource/r1").mock(
        return_value=Response(200, json={"labels": [{"tag_key": "added", "tag_value": "yes"}]})
    )
    result = client.patch_labels("r1", add={"added": "yes"})
    assert result[0].key == "added"


@respx.mock
def test_patch_labels_remove_only(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/labels/resource/r1").mock(
        return_value=Response(200, json={"labels": [{"tag_key": "key1", "tag_value": "v1"}, {"tag_key": "key2", "tag_value": "v2"}]})
    )
    respx.put(f"{BASE_URL}/api/v1/labels/resource/r1").mock(
        return_value=Response(200, json={"labels": []})
    )
    result = client.patch_labels("r1", remove=["key1", "key2"])
    assert len(result) == 0


@respx.mock
def test_list_all_tags(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/labels").mock(
        return_value=Response(200, json={"items": [{"tag_key": "modality", "tag_value": "MRI"}, {"tag_key": "modality", "tag_value": "MRI"}, {"tag_key": "site", "tag_value": "A"}]})
    )
    result = client.list_all_tags()
    assert len(result) == 2
    assert result[0].count == 2


@respx.mock
def test_list_all_tags_uses_server_counts(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/labels").mock(
        return_value=Response(200, json={"items": [{"tag_key": "modality", "tag_value": "MRI", "count": 7}]})
    )
    result = client.list_all_tags()
    assert len(result) == 1
    assert result[0].count == 7


@respx.mock
def test_list_all_tags_dict_response(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/labels").mock(
        return_value=Response(200, json={"items": [{"tag_key": "t1", "tag_value": "v1"}]})
    )
    result = client.list_all_tags()
    assert len(result) == 1


@respx.mock
def test_batch_label(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/labels/batch").mock(
        return_value=Response(200, json={"processed": 2})
    )
    ops = [
        BatchLabelOperation(resource_id="r1", operation="add", add={"k1": "v1"}),
        BatchLabelOperation(resource_id="r2", operation="remove", remove=["k2"]),
    ]
    result = client.batch_label(ops)
    assert result["processed"] == 2


@respx.mock
def test_batch_label_expands_multiple_removes(client: VnaClient) -> None:
    route = respx.post(f"{BASE_URL}/api/v1/labels/batch").mock(
        return_value=Response(200, json={"processed": 2})
    )
    ops = [BatchLabelOperation(resource_id="r1", operation="remove", remove=["k1", "k2"])]
    result = client.batch_label(ops)
    assert result["processed"] == 2
    assert json.loads(route.calls[0].request.content) == {
        "operations": [
            {"action": "remove", "resource_id": "r1", "tag_key": "k1"},
            {"action": "remove", "resource_id": "r1", "tag_key": "k2"},
        ]
    }


@respx.mock
def test_register_resource_normalizes_legacy_source_type(client: VnaClient) -> None:
    route = respx.post(f"{BASE_URL}/api/v1/resources").mock(
        return_value=Response(201, json={
            "resource_id": "new-2",
            "patient_ref": "p1",
            "source_type": "dicom_only",
            "data_type": "dicom",
            "labels": [],
            "metadata": {},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        })
    )
    result = client.register_resource(patient_ref="p1", source_type=SourceType.DICOM)
    assert result.source_type == "dicom_only"
    assert json.loads(route.calls[0].request.content)["source_type"] == "dicom_only"


# ─── Query ─────────────────────────────────────────────────────────────────────

@respx.mock
def test_query(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/query").mock(
        return_value=Response(200, json={"total": 3, "limit": 50, "offset": 0, "items": [
            {"resource_id": f"r{i}", "patient_ref": "p1", "source_type": "dicom", "data_type": "imaging", "labels": [], "metadata": {}, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}
            for i in range(3)
        ]})
    )
    result = client.query(patient_ref="p1")
    assert result.total == 3
    assert len(result.resources) == 3


@respx.mock
def test_query_with_search(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/query").mock(
        return_value=Response(200, json={"total": 0, "limit": 50, "offset": 0, "items": []})
    )
    result = client.query(search="brain MRI")
    assert result.total == 0


# ─── Server Management ─────────────────────────────────────────────────────────

@respx.mock
def test_register_server(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/sync/register").mock(
        return_value=Response(200, json={"source_db": "dicom", "url": "http://dcm:4242", "server_id": "srv-1", "registered_at": "2026-01-01T00:00:00Z"})
    )
    result = client.register_server("dicom", "http://dcm:4242", "test-dcm")
    assert result.server_id == "srv-1"
    assert result.server_type == "dicom"


# ─── Sync ──────────────────────────────────────────────────────────────────────

@respx.mock
def test_sync_status(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/sync/status").mock(
        return_value=Response(200, json={"dicom": {"status": "idle"}, "bids": {"status": "idle"}, "last_sync": "2026-01-01T00:00:00Z", "events": []})
    )
    result = client.sync_status()
    assert result.dicom["status"] == "idle"


@respx.mock
def test_trigger_sync(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/sync/trigger").mock(
        return_value=Response(200, json={"triggered": True, "pending_events": 4, "processed_events": 2, "source_db": "dicom"})
    )
    result = client.trigger_sync("dicom")
    assert result.triggered is True
    assert result.source_db == "dicom"


@respx.mock
def test_trigger_sync_with_enum(client: VnaClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/sync/trigger").mock(
        return_value=Response(200, json={"triggered": True, "pending_events": 3, "processed_events": 1, "source_db": "bids"})
    )
    result = client.trigger_sync(SourceType.BIDS)
    assert result.source_db == "bids"


# ─── Error Handling ─────────────────────────────────────────────────────────────

@respx.mock
def test_request_error(client: VnaClient) -> None:
    """Test connection error handling."""
    respx.get(f"{BASE_URL}/api/v1/health").mock(side_effect=httpx.ConnectError("Connection refused"))
    with pytest.raises(VnaClientError) as exc:
        client.health()
    assert "Request failed" in str(exc.value)


@respx.mock
def test_error_with_detail(client: VnaClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/resources/bad").mock(
        return_value=Response(400, json={"detail": "Invalid resource ID format"})
    )
    with pytest.raises(VnaClientError) as exc:
        client.get_resource("bad")
    assert exc.value.status_code == 400
    assert exc.value.detail["detail"] == "Invalid resource ID format"


# ─── Context Manager ───────────────────────────────────────────────────────────

def test_context_manager() -> None:
    with VnaClient(base_url=BASE_URL) as c:
        assert c.base_url == BASE_URL


# ─── API Key ────────────────────────────────────────────────────────────────────

def test_api_key_header() -> None:
    c = VnaClient(base_url=BASE_URL, api_key="test-key-123")
    assert c._headers["Authorization"] == "Bearer test-key-123"
    c.close()
