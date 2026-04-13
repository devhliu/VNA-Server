"""Tests for treatment timeline API."""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_create_treatment(test_client: AsyncClient):
    resp = await test_client.post("/api/v1/treatments", json={
        "patient_ref": "pt-treat-1",
        "event_type": "surgery",
        "event_date": "2026-01-15T10:00:00Z",
        "description": "Tumor resection",
        "facility": "Hospital A",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["event_type"] == "surgery"
    assert data["patient_ref"] == "pt-treat-1"


@pytest.mark.asyncio
async def test_list_treatments(test_client: AsyncClient):
    await test_client.post("/api/v1/treatments", json={
        "patient_ref": "pt-list-1",
        "event_type": "chemotherapy",
    })
    await test_client.post("/api/v1/treatments", json={
        "patient_ref": "pt-list-1",
        "event_type": "radiation",
    })

    resp = await test_client.get("/api/v1/treatments")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 2

    # Filter by patient
    resp = await test_client.get("/api/v1/treatments", params={"patient_ref": "pt-list-1"})
    assert resp.status_code == 200
    assert all(e["patient_ref"] == "pt-list-1" for e in resp.json()["items"])


@pytest.mark.asyncio
async def test_timeline(test_client: AsyncClient):
    await test_client.post("/api/v1/treatments", json={
        "patient_ref": "pt-timeline",
        "event_type": "surgery",
        "event_date": "2026-01-01T00:00:00Z",
    })
    await test_client.post("/api/v1/treatments", json={
        "patient_ref": "pt-timeline",
        "event_type": "chemotherapy",
        "event_date": "2026-02-01T00:00:00Z",
    })

    resp = await test_client.get("/api/v1/timeline/pt-timeline")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) >= 2
    # Timeline should be ordered by date ascending
    dates = [e["event_date"] for e in events if e["event_date"]]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_update_treatment(test_client: AsyncClient):
    create_resp = await test_client.post("/api/v1/treatments", json={
        "patient_ref": "pt-update",
        "event_type": "surgery",
        "description": "Before",
    })
    event_id = create_resp.json()["id"]

    resp = await test_client.put(f"/api/v1/treatments/{event_id}", json={
        "description": "After",
        "outcome": "Successful",
    })
    assert resp.status_code == 200
    assert resp.json()["description"] == "After"


@pytest.mark.asyncio
async def test_delete_treatment(test_client: AsyncClient):
    create_resp = await test_client.post("/api/v1/treatments", json={
        "patient_ref": "pt-delete",
        "event_type": "follow_up",
    })
    event_id = create_resp.json()["id"]

    resp = await test_client.delete(f"/api/v1/treatments/{event_id}")
    assert resp.status_code == 204

    resp = await test_client.get(f"/api/v1/treatments/{event_id}")
    assert resp.status_code == 404
