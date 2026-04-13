"""Integration tests for VNA Main Server - resources, patients, labels, webhooks, sync."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from vna_main.main import app


@pytest.fixture
async def http_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestResourcesAPI:
    @pytest.mark.asyncio
    async def test_create_resource(self, http_client: AsyncClient):
        resp = await http_client.post("/api/v1/resources", json={
            "source_type": "dicom_only",
            "data_type": "dicom",
            "dicom_study_uid": "1.2.3.4.5",
            "file_name": "CT_001.dcm",
            "file_size": 102400,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["resource_id"].startswith("res-")
        assert data["dicom_study_uid"] == "1.2.3.4.5"
        assert data["source_type"] == "dicom_only"

    @pytest.mark.asyncio
    async def test_list_resources(self, http_client: AsyncClient):
        for i in range(3):
            await http_client.post("/api/v1/resources", json={
                "source_type": f"dicom_only",
                "data_type": "dicom",
            })

        resp = await http_client.get("/api/v1/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert len(data["items"]) >= 3

    @pytest.mark.asyncio
    async def test_get_resource(self, http_client: AsyncClient):
        create_resp = await http_client.post("/api/v1/resources", json={
            "source_type": "dicom_only",
            "data_type": "dicom",
        })
        resource_id = create_resp.json()["resource_id"]

        resp = await http_client.get(f"/api/v1/resources/{resource_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resource_id"] == resource_id

    @pytest.mark.asyncio
    async def test_get_resource_not_found(self, http_client: AsyncClient):
        resp = await http_client.get("/api/v1/resources/res-nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_resource(self, http_client: AsyncClient):
        create_resp = await http_client.post("/api/v1/resources", json={
            "source_type": "dicom_only",
            "data_type": "dicom",
        })
        resource_id = create_resp.json()["resource_id"]

        resp = await http_client.delete(f"/api/v1/resources/{resource_id}")
        assert resp.status_code == 200

        resp = await http_client.get(f"/api/v1/resources/{resource_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_resource(self, http_client: AsyncClient):
        create_resp = await http_client.post("/api/v1/resources", json={
            "source_type": "dicom_only",
            "data_type": "dicom",
        })
        resource_id = create_resp.json()["resource_id"]

        resp = await http_client.patch(f"/api/v1/resources/{resource_id}", json={
            "file_name": "updated.dcm",
        })
        assert resp.status_code == 200
        assert resp.json()["file_name"] == "updated.dcm"


class TestPatientsAPI:
    @pytest.mark.asyncio
    async def test_create_patient(self, http_client: AsyncClient):
        resp = await http_client.post("/api/v1/patients", json={
            "hospital_id": "H001",
            "source": "hospitalA",
            "external_system": "PACS",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_ref"].startswith("pt-")
        assert data["hospital_id"] == "H001"

    @pytest.mark.asyncio
    async def test_list_patients(self, http_client: AsyncClient):
        for i in range(2):
            await http_client.post("/api/v1/patients", json={
                "hospital_id": f"H{i:02d}",
                "source": "hospitalA",
            })

        resp = await http_client.get("/api/v1/patients")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.asyncio
    async def test_get_patient(self, http_client: AsyncClient):
        create_resp = await http_client.post("/api/v1/patients", json={
            "patient_ref": "pt-get-test",
            "hospital_id": "H100",
            "source": "hospitalA",
        })
        assert create_resp.status_code == 201

        resp = await http_client.get("/api/v1/patients/pt-get-test")
        assert resp.status_code == 200
        assert resp.json()["hospital_id"] == "H100"

    @pytest.mark.asyncio
    async def test_delete_patient(self, http_client: AsyncClient):
        create_resp = await http_client.post("/api/v1/patients", json={
            "hospital_id": "HDel",
            "source": "hospitalA",
        })
        patient_ref = create_resp.json()["patient_ref"]

        resp = await http_client.delete(f"/api/v1/patients/{patient_ref}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_patient_resources(self, http_client: AsyncClient):
        patient_resp = await http_client.post("/api/v1/patients", json={
            "hospital_id": "HRes",
            "source": "hospitalA",
        })
        patient_ref = patient_resp.json()["patient_ref"]

        for _ in range(2):
            await http_client.post("/api/v1/resources", json={
                "patient_ref": patient_ref,
                "source_type": "dicom_only",
                "data_type": "dicom",
            })

        resp = await http_client.get(f"/api/v1/patients/{patient_ref}/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2


class TestLabelsAPI:
    @pytest.mark.asyncio
    async def test_set_labels(self, http_client: AsyncClient):
        resp = await http_client.post("/api/v1/resources", json={
            "source_type": "dicom_only",
            "data_type": "dicom",
        })
        resource_id = resp.json()["resource_id"]

        resp = await http_client.put(f"/api/v1/labels/resource/{resource_id}", json={
            "labels": [
                {"tag_key": "modality", "tag_value": "CT", "tag_type": "system"},
                {"tag_key": "project", "tag_value": "lung-cancer", "tag_type": "custom"},
            ],
            "tagged_by": "admin",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["labels"]) == 2

    @pytest.mark.asyncio
    async def test_get_resource_labels(self, http_client: AsyncClient):
        resp = await http_client.post("/api/v1/resources", json={
            "source_type": "dicom_only",
            "data_type": "dicom",
        })
        resource_id = resp.json()["resource_id"]

        await http_client.put(f"/api/v1/labels/resource/{resource_id}", json={
            "labels": [{"tag_key": "task", "tag_value": "rest", "tag_type": "custom"}],
        })

        resp = await http_client.get(f"/api/v1/labels/resource/{resource_id}")
        assert resp.status_code == 200
        assert len(resp.json()["labels"]) == 1

    @pytest.mark.asyncio
    async def test_patch_labels(self, http_client: AsyncClient):
        resp = await http_client.post("/api/v1/resources", json={
            "source_type": "dicom_only",
            "data_type": "dicom",
        })
        resource_id = resp.json()["resource_id"]

        await http_client.put(f"/api/v1/labels/resource/{resource_id}", json={
            "labels": [{"tag_key": "modality", "tag_value": "CT"}],
        })

        resp = await http_client.patch(f"/api/v1/labels/resource/{resource_id}", json={
            "labels": [{"tag_key": "modality", "tag_value": "MR"}],
        })
        assert resp.status_code == 200
        labels = resp.json()["labels"]
        assert any(l["tag_value"] == "MR" for l in labels)

    @pytest.mark.asyncio
    async def test_label_history(self, http_client: AsyncClient):
        resp = await http_client.post("/api/v1/resources", json={
            "source_type": "dicom_only",
            "data_type": "dicom",
        })
        resource_id = resp.json()["resource_id"]

        await http_client.put(f"/api/v1/labels/resource/{resource_id}", json={
            "labels": [{"tag_key": "status", "tag_value": "reviewed", "tag_type": "custom"}],
            "tagged_by": "radiologist_a",
        })

        await http_client.put(f"/api/v1/labels/resource/{resource_id}", json={
            "labels": [{"tag_key": "status", "tag_value": "final", "tag_type": "custom"}],
            "tagged_by": "radiologist_b",
        })

        resp = await http_client.get("/api/v1/labels/history", params={"resource_id": resource_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

        actions = [item["action"] for item in data["items"]]
        assert "created" in actions
        assert "deleted" in actions


class TestQueryAPI:
    @pytest.mark.asyncio
    async def test_unified_query(self, http_client: AsyncClient):
        patient_resp = await http_client.post("/api/v1/patients", json={
            "hospital_id": "HQuery",
            "source": "hospitalA",
        })
        patient_ref = patient_resp.json()["patient_ref"]

        for i in range(3):
            await http_client.post("/api/v1/resources", json={
                "patient_ref": patient_ref,
                "source_type": "dicom_only",
                "data_type": "dicom",
                "dicom_study_uid": f"1.2.3.4.{i}",
            })

        resp = await http_client.post("/api/v1/query", json={
            "hospital_id": "HQuery",
            "limit": 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3

    @pytest.mark.asyncio
    async def test_query_by_source_type(self, http_client: AsyncClient):
        for src in ("dicom_only", "bids_only"):
            await http_client.post("/api/v1/resources", json={
                "source_type": src,
                "data_type": "dicom" if src == "dicom_only" else "nifti",
            })

        resp = await http_client.post("/api/v1/query", json={
            "source_type": "dicom_only",
            "limit": 10,
        })
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(item["source_type"] == "dicom_only" for item in items)

    @pytest.mark.asyncio
    async def test_query_empty(self, http_client: AsyncClient):
        resp = await http_client.post("/api/v1/query", json={
            "dicom_study_uid": "nonexistent-uid-99999",
            "limit": 10,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestSyncAPI:
    @pytest.mark.asyncio
    async def test_list_sync_events(self, http_client: AsyncClient):
        resp = await http_client.get("/api/v1/sync/events")
        assert resp.status_code == 200
        assert "items" in resp.json()

    @pytest.mark.asyncio
    async def test_get_sync_status(self, http_client: AsyncClient):
        resp = await http_client.get("/api/v1/sync/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "dicom" in data
        assert "bids" in data


class TestWebhookAPI:
    @pytest.mark.asyncio
    async def test_create_webhook(self, http_client: AsyncClient):
        resp = await http_client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["resource.created", "resource.updated"],
            "description": "Test webhook",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "https://example.com/webhook"
        assert data["events"] == ["resource.created", "resource.updated"]
        assert "secret" in data
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_list_webhooks(self, http_client: AsyncClient):
        await http_client.post("/api/v1/webhooks", json={
            "url": "https://example.com/wh1",
            "events": ["resource.created"],
        })
        await http_client.post("/api/v1/webhooks", json={
            "url": "https://example.com/wh2",
            "events": ["resource.deleted"],
        })

        resp = await http_client.get("/api/v1/webhooks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 2

    @pytest.mark.asyncio
    async def test_get_webhook(self, http_client: AsyncClient):
        create_resp = await http_client.post("/api/v1/webhooks", json={
            "url": "https://example.com/get-test",
            "events": ["resource.created"],
        })
        wh_id = create_resp.json()["id"]

        resp = await http_client.get(f"/api/v1/webhooks/{wh_id}")
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://example.com/get-test"

    @pytest.mark.asyncio
    async def test_update_webhook(self, http_client: AsyncClient):
        create_resp = await http_client.post("/api/v1/webhooks", json={
            "url": "https://example.com/update-test",
            "events": ["resource.created"],
        })
        wh_id = create_resp.json()["id"]

        resp = await http_client.patch(f"/api/v1/webhooks/{wh_id}", json={
            "events": ["resource.deleted"],
            "enabled": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == ["resource.deleted"]
        assert data["enabled"] is False

    @pytest.mark.asyncio
    async def test_delete_webhook(self, http_client: AsyncClient):
        create_resp = await http_client.post("/api/v1/webhooks", json={
            "url": "https://example.com/del-test",
            "events": ["resource.created"],
        })
        wh_id = create_resp.json()["id"]

        resp = await http_client.delete(f"/api/v1/webhooks/{wh_id}")
        assert resp.status_code == 200

        resp = await http_client.get(f"/api/v1/webhooks/{wh_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_webhook_stats(self, http_client: AsyncClient):
        await http_client.post("/api/v1/webhooks", json={
            "url": "https://example.com/stats-test",
            "events": ["resource.created"],
            "enabled": True,
        })
        await http_client.post("/api/v1/webhooks", json={
            "url": "https://example.com/stats-test2",
            "events": ["resource.deleted"],
            "enabled": False,
        })

        resp = await http_client.get("/api/v1/webhooks/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert data["enabled"] >= 1
        assert "event_counts" in data

    @pytest.mark.asyncio
    async def test_webhook_delivery_logs(self, http_client: AsyncClient):
        create_resp = await http_client.post("/api/v1/webhooks", json={
            "url": "https://example.com/logs-test",
            "events": ["resource.created"],
        })
        wh_id = create_resp.json()["id"]

        resp = await http_client.get(f"/api/v1/webhooks/{wh_id}/deliveries")
        assert resp.status_code == 200
        assert "items" in resp.json()


class TestPatientSyncAPI:
    @pytest.mark.asyncio
    async def test_sync_status(self, http_client: AsyncClient):
        resp = await http_client.get("/api/v1/patients/sync-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_patients" in data
        assert "dicom_patients" in data
        assert "bids_patients" in data
        assert "total_resources" in data
        assert "mapped_resources" in data


class TestHealthAPI:
    @pytest.mark.asyncio
    async def test_root(self, http_client: AsyncClient):
        resp = await http_client.get("/")
        assert resp.status_code == 200
        assert resp.json()["service"] == "vna-main-server"

    @pytest.mark.asyncio
    async def test_health(self, http_client: AsyncClient):
        resp = await http_client.get("/api/v1/health")
        assert resp.status_code == 200
