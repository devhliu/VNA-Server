"""Tests for patient API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_patients_empty(test_client: AsyncClient):
    """GET /v1/patients returns empty list."""
    resp = await test_client.get("/api/v1/patients")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_patient(test_client: AsyncClient):
    """POST /v1/patients creates a patient."""
    payload = {
        "hospital_id": "HOSP001",
        "source": "manual",
    }
    resp = await test_client.post("/api/v1/patients", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["hospital_id"] == "HOSP001"
    assert data["source"] == "manual"
    assert "patient_ref" in data
    assert data["patient_ref"].startswith("pt-")


@pytest.mark.asyncio
async def test_create_patient_with_external_system(test_client: AsyncClient):
    """POST /v1/patients with external_system field."""
    payload = {
        "hospital_id": "HOSP002",
        "source": "dicom_auto",
        "external_system": "orthanc",
    }
    resp = await test_client.post("/api/v1/patients", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["external_system"] == "orthanc"


@pytest.mark.asyncio
async def test_get_patient(test_client: AsyncClient):
    """GET /v1/patients/{ref} returns patient details."""
    # Create first
    create_resp = await test_client.post("/api/v1/patients", json={
        "hospital_id": "HOSP003",
        "source": "manual",
    })
    patient_ref = create_resp.json()["patient_ref"]

    resp = await test_client.get(f"/api/v1/patients/{patient_ref}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_ref"] == patient_ref
    assert data["hospital_id"] == "HOSP003"
    assert "resources" in data


@pytest.mark.asyncio
async def test_get_patient_not_found(test_client: AsyncClient):
    """GET /v1/patients/{ref} returns 404 for missing patient."""
    resp = await test_client.get("/api/v1/patients/nonexistent-ref")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_patient(test_client: AsyncClient):
    """PUT /v1/patients/{ref} updates a patient."""
    create_resp = await test_client.post("/api/v1/patients", json={
        "hospital_id": "HOSP004",
        "source": "manual",
    })
    patient_ref = create_resp.json()["patient_ref"]

    resp = await test_client.put(f"/api/v1/patients/{patient_ref}", json={
        "hospital_id": "HOSP004-UPDATED",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["hospital_id"] == "HOSP004-UPDATED"


@pytest.mark.asyncio
async def test_delete_patient(test_client: AsyncClient):
    """DELETE /v1/patients/{ref} deletes a patient."""
    create_resp = await test_client.post("/api/v1/patients", json={
        "hospital_id": "HOSP005",
        "source": "manual",
    })
    patient_ref = create_resp.json()["patient_ref"]

    resp = await test_client.delete(f"/api/v1/patients/{patient_ref}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == patient_ref

    # Verify it's gone
    resp2 = await test_client.get(f"/api/v1/patients/{patient_ref}")
    assert resp2.status_code == 404
