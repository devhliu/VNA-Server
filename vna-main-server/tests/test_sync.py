"""Tests for sync service endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sync_status_empty(test_client: AsyncClient):
    """GET /v1/sync/status returns empty status when no servers registered."""
    resp = await test_client.get("/v1/sync/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "dicom" in data
    assert "bids" in data
    assert "total_pending" in data


@pytest.mark.asyncio
async def test_receive_sync_event(test_client: AsyncClient):
    """POST /v1/sync/event creates a sync event."""
    payload = {
        "source_db": "dicom",
        "event_type": "resource.created",
        "resource_id": "test-res-001",
        "payload": {"source_type": "dicom_only", "data_type": "dicom"},
    }
    resp = await test_client.post("/v1/sync/event", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert data["source_db"] == "dicom"
    assert data["event_type"] == "resource.created"
    assert data["processed"] is False


@pytest.mark.asyncio
async def test_trigger_sync(test_client: AsyncClient):
    """POST /v1/sync/trigger processes pending events."""
    # Create an event first
    await test_client.post("/v1/sync/event", json={
        "source_db": "dicom",
        "event_type": "resource.created",
        "resource_id": "test-res-002",
        "payload": {"source_type": "dicom_only", "data_type": "dicom"},
    })
    resp = await test_client.post("/v1/sync/trigger?source_db=dicom")
    assert resp.status_code == 200
    data = resp.json()
    assert data["triggered"] is True
    assert data["source_db"] == "dicom"
    assert "pending_events" in data
    assert "processed_events" in data


@pytest.mark.asyncio
async def test_internal_sync_dicom(test_client: AsyncClient):
    """POST /v1/internal/sync/dicom receives Orthanc events."""
    payload = {
        "event_type": "dicom_received",
        "orthanc_id": "orthanc-001",
        "study_uid": "1.2.3.4",
        "patient_id": "PAT001",
        "patient_name": "Test^Patient",
    }
    resp = await test_client.post("/v1/internal/sync/dicom", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["received"] is True
    assert "event_id" in data


@pytest.mark.asyncio
async def test_list_sync_events(test_client: AsyncClient):
    """GET /v1/sync/events lists sync events."""
    await test_client.post("/v1/sync/event", json={
        "source_db": "bids",
        "event_type": "bids_completed",
        "resource_id": "test-res-003",
    })
    resp = await test_client.get("/v1/sync/events")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert data["total"] >= 1
