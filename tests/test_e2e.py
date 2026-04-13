"""End-to-end integration tests using real Docker Compose services.

These tests require the full VNA stack to be running.
Run with: pytest tests/test_e2e.py -v -m integration --timeout=120

Requires environment variables:
  ORTHANC_URL=http://localhost:8042
  MAIN_SERVER_URL=http://localhost:8000
  BIDS_SERVER_URL=http://localhost:8080
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import pytest

ORTHANC_URL = os.environ.get("ORTHANC_URL", "http://localhost:8042")
MAIN_URL = os.environ.get("MAIN_SERVER_URL", "http://localhost:8000")
BIDS_URL = os.environ.get("BIDS_SERVER_URL", "http://localhost:8080")


def wait_for_service(url: str, path: str = "/", timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{url}{path}", timeout=5.0)
            if resp.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


@pytest.fixture(scope="session", autouse=True)
def ensure_services(docker_services, wait_for_service):
    assert wait_for_service(ORTHANC_URL, "/system"), "Orthanc not available"
    assert wait_for_service(MAIN_URL, "/"), "Main server not available"
    assert wait_for_service(BIDS_URL, "/health"), "BIDS server not available"


class TestDicomServerE2E:
    """End-to-end tests against real Orthanc instance."""

    def test_orthanc_system_info(self):
        resp = httpx.get(f"{ORTHANC_URL}/system", timeout=10.0)
        assert resp.status_code == 200
        data = resp.json()
        assert "Version" in data
        assert "Database" in data

    def test_orthanc_statistics(self):
        resp = httpx.get(f"{ORTHANC_URL}/statistics", timeout=10.0)
        assert resp.status_code == 200
        data = resp.json()
        assert "CountStudies" in data
        assert "CountInstances" in data

    def test_orthanc_modalities(self):
        resp = httpx.get(f"{ORTHANC_URL}/modalities", timeout=10.0)
        assert resp.status_code == 200

    def test_orthanc_patients_empty(self):
        resp = httpx.get(f"{ORTHANC_URL}/patients?limit=100", timeout=10.0)
        assert resp.status_code == 200
        assert isinstance(resp.json(), (list, dict))


class TestMainServerE2E:
    """End-to-end tests against real VNA Main Server."""

    def test_main_root(self):
        resp = httpx.get(f"{MAIN_URL}/", timeout=10.0)
        assert resp.status_code == 200
        assert resp.json()["service"] == "vna-main-server"

    def test_main_health(self):
        resp = httpx.get(f"{MAIN_URL}/v1/health", timeout=10.0)
        assert resp.status_code == 200

    def test_main_create_resource(self):
        resp = httpx.post(
            f"{MAIN_URL}/v1/resources",
            json={"source_type": "dicom_only", "data_type": "dicom", "dicom_study_uid": "1.2.3.4.5"},
            timeout=10.0,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["resource_id"].startswith("res-")

    def test_main_patient_mapping(self):
        resp = httpx.post(
            f"{MAIN_URL}/v1/patients",
            json={"hospital_id": "H_E2E", "source": "e2e_test"},
            timeout=10.0,
        )
        assert resp.status_code == 201
        patient_ref = resp.json()["patient_ref"]

        resp = httpx.get(f"{MAIN_URL}/v1/patients/{patient_ref}", timeout=10.0)
        assert resp.status_code == 200
        assert resp.json()["hospital_id"] == "H_E2E"

    def test_main_webhook_lifecycle(self):
        resp = httpx.post(
            f"{MAIN_URL}/v1/webhooks",
            json={
                "url": "https://httpbin.org/post",
                "events": ["resource.created"],
                "description": "E2E test",
            },
            timeout=10.0,
        )
        assert resp.status_code == 200
        data = resp.json()
        wh_id = data["id"]
        assert data["enabled"] is True

        resp = httpx.get(f"{MAIN_URL}/v1/webhooks/{wh_id}", timeout=10.0)
        assert resp.status_code == 200

        resp = httpx.delete(f"{MAIN_URL}/v1/webhooks/{wh_id}", timeout=10.0)
        assert resp.status_code == 200

    def test_main_labels_with_history(self):
        resp = httpx.post(
            f"{MAIN_URL}/v1/resources",
            json={"source_type": "dicom_only", "data_type": "dicom"},
            timeout=10.0,
        )
        resource_id = resp.json()["resource_id"]

        httpx.put(
            f"{MAIN_URL}/v1/labels/resource/{resource_id}",
            json={"labels": [{"tag_key": "status", "tag_value": "pending"}], "tagged_by": "e2e"},
            timeout=10.0,
        )

        httpx.put(
            f"{MAIN_URL}/v1/labels/resource/{resource_id}",
            json={"labels": [{"tag_key": "status", "tag_value": "reviewed"}], "tagged_by": "e2e"},
            timeout=10.0,
        )

        resp = httpx.get(f"{MAIN_URL}/v1/labels/history?resource_id={resource_id}", timeout=10.0)
        assert resp.status_code == 200
        history = resp.json()["items"]
        actions = {item["action"] for item in history}
        assert "created" in actions
        assert "deleted" in actions

    def test_main_patient_sync_status(self):
        resp = httpx.get(f"{MAIN_URL}/v1/patients/sync-status", timeout=10.0)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_patients" in data
        assert "dicom_patients" in data


class TestDicomSDKToServerE2E:
    """E2E tests for DICOM SDK against real Orthanc instance."""

    def test_dicom_client_system(self):
        from dicom_sdk import DicomClient
        with DicomClient(ORTHANC_URL, username="orthanc", password="orthanc") as client:
            info = client.get_system()
            assert "Version" in info
        assert True

    def test_dicom_client_statistics(self):
        from dicom_sdk import DicomClient
        with DicomClient(ORTHANC_URL, username="orthanc", password="orthanc") as client:
            stats = client.get_statistics()
            assert hasattr(stats, "count_studies")
            assert hasattr(stats, "count_instances")

    def test_dicom_client_list_modalities(self):
        from dicom_sdk import DicomClient
        with DicomClient(ORTHANC_URL, username="orthanc", password="orthanc") as client:
            modalities = client.list_modalities()
            assert isinstance(modalities, list)


class TestCrossServerE2E:
    """E2E tests verifying cross-server communication."""

    def test_main_server_dicom_health_check(self):
        resp = httpx.get(f"{MAIN_URL}/v1/sync/health", timeout=10.0)
        assert resp.status_code == 200
        data = resp.json()
        assert "overall" in data or "dicom" in data or "bids" in data
