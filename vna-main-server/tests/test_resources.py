"""Tests for resource API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_resources(test_client: AsyncClient):
    """GET /v1/resources returns resources."""
    resp = await test_client.get("/api/v1/resources")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_create_resource(test_client: AsyncClient):
    """POST /v1/resources creates a resource."""
    payload = {
        "data_type": "dicom",
        "source_type": "dicom_only",
        "file_name": "test.dcm",
        "file_size": 1024,
    }
    resp = await test_client.post("/api/v1/resources", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["data_type"] == "dicom"
    assert data["source_type"] == "dicom_only"
    assert data["file_name"] == "test.dcm"
    assert data["resource_id"].startswith("res-")


@pytest.mark.asyncio
async def test_create_resource_with_metadata(test_client: AsyncClient):
    """POST /v1/resources with metadata field."""
    payload = {
        "data_type": "dicom",
        "source_type": "dicom_only",
        "metadata": {"study_uid": "1.2.3.4", "patient": "P001"},
    }
    resp = await test_client.post("/api/v1/resources", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["metadata"] == {"study_uid": "1.2.3.4", "patient": "P001"}


@pytest.mark.asyncio
async def test_get_resource(test_client: AsyncClient):
    """GET /v1/resources/{id} returns resource details."""
    create_resp = await test_client.post("/api/v1/resources", json={
        "data_type": "dicom",
        "source_type": "dicom_only",
        "dicom_study_uid": "1.2.3.4.5",
    })
    resource_id = create_resp.json()["resource_id"]

    resp = await test_client.get(f"/api/v1/resources/{resource_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resource_id"] == resource_id
    assert data["dicom_study_uid"] == "1.2.3.4.5"


@pytest.mark.asyncio
async def test_get_resource_not_found(test_client: AsyncClient):
    """GET /v1/resources/{id} returns 404 for missing resource."""
    resp = await test_client.get("/api/v1/resources/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_resource(test_client: AsyncClient):
    """PUT /v1/resources/{id} updates a resource."""
    create_resp = await test_client.post("/api/v1/resources", json={
        "data_type": "dicom",
        "file_name": "original.dcm",
    })
    resource_id = create_resp.json()["resource_id"]

    resp = await test_client.put(f"/api/v1/resources/{resource_id}", json={
        "file_name": "updated.dcm",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_name"] == "updated.dcm"


@pytest.mark.asyncio
async def test_delete_resource(test_client: AsyncClient):
    """DELETE /v1/resources/{id} deletes a resource."""
    create_resp = await test_client.post("/api/v1/resources", json={
        "data_type": "dicom",
    })
    resource_id = create_resp.json()["resource_id"]

    resp = await test_client.delete(f"/api/v1/resources/{resource_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == resource_id

    resp2 = await test_client.get(f"/api/v1/resources/{resource_id}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_resource_with_patient(test_client: AsyncClient):
    """Resource can be linked to a patient."""
    # Create patient
    pat_resp = await test_client.post("/api/v1/patients", json={
        "hospital_id": "HOSP-R1",
        "source": "manual",
    })
    patient_ref = pat_resp.json()["patient_ref"]

    # Create resource linked to patient
    res_resp = await test_client.post("/api/v1/resources", json={
        "data_type": "dicom",
        "patient_ref": patient_ref,
    })
    assert res_resp.status_code == 201
    data = res_resp.json()
    assert data["patient_ref"] == patient_ref

    # Verify patient's resources
    pat_resources = await test_client.get(f"/api/v1/patients/{patient_ref}/resources")
    assert pat_resources.status_code == 200
    assert pat_resources.json()["total"] == 1
