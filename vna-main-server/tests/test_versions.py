"""Tests for version API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_resource_version(test_client: AsyncClient):
    """POST /v1/versions/resources/{id}/versions creates a version."""
    res_resp = await test_client.post("/v1/resources", json={
        "data_type": "dicom",
        "source_type": "dicom_only",
        "file_name": "version-test.dcm",
    })
    resource_id = res_resp.json()["resource_id"]

    resp = await test_client.post(
        f"/v1/versions/resources/{resource_id}/versions",
        json={"change_type": "update", "change_description": "Test version"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resource_id"] == resource_id
    assert data["version_number"] == 1
    assert data["change_type"] == "update"


@pytest.mark.asyncio
async def test_create_version_nonexistent_resource(test_client: AsyncClient):
    """POST /v1/versions/resources/{id}/versions returns 404 for missing resource."""
    resp = await test_client.post(
        "/v1/versions/resources/nonexistent-res/versions",
        json={"change_type": "update"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_resource_versions(test_client: AsyncClient):
    """GET /v1/versions/resources/{id}/versions lists versions."""
    res_resp = await test_client.post("/v1/resources", json={
        "data_type": "dicom",
        "source_type": "dicom_only",
        "file_name": "version-test.dcm",
    })
    resource_id = res_resp.json()["resource_id"]

    # Create two versions
    await test_client.post(
        f"/v1/versions/resources/{resource_id}/versions",
        json={"change_type": "update"},
    )
    await test_client.post(
        f"/v1/versions/resources/{resource_id}/versions",
        json={"change_type": "update"},
    )

    resp = await test_client.get(f"/v1/versions/resources/{resource_id}/versions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resource_id"] == resource_id
    assert data["total"] == 2
    assert len(data["versions"]) == 2


@pytest.mark.asyncio
async def test_create_snapshot(test_client: AsyncClient):
    """POST /v1/versions/snapshots creates a snapshot."""
    resp = await test_client.post("/v1/versions/snapshots", json={
        "name": "test-snapshot",
        "description": "A test snapshot",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-snapshot"
    assert "snapshot_id" in data
    assert data["snapshot_id"].startswith("snap-")


@pytest.mark.asyncio
async def test_list_snapshots(test_client: AsyncClient):
    """GET /v1/versions/snapshots lists snapshots."""
    await test_client.post("/v1/versions/snapshots", json={
        "name": "snap-1",
    })

    resp = await test_client.get("/v1/versions/snapshots")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "snapshots" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_snapshot(test_client: AsyncClient):
    """GET /v1/versions/snapshots/{id} returns snapshot details."""
    create_resp = await test_client.post("/v1/versions/snapshots", json={
        "name": "snap-get-test",
    })
    snapshot_id = create_resp.json()["snapshot_id"]

    resp = await test_client.get(f"/v1/versions/snapshots/{snapshot_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["snapshot_id"] == snapshot_id
    assert data["name"] == "snap-get-test"


@pytest.mark.asyncio
async def test_delete_snapshot(test_client: AsyncClient):
    """DELETE /v1/versions/snapshots/{id} deletes a snapshot."""
    create_resp = await test_client.post("/v1/versions/snapshots", json={
        "name": "snap-delete-test",
    })
    snapshot_id = create_resp.json()["snapshot_id"]

    resp = await test_client.delete(f"/v1/versions/snapshots/{snapshot_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    resp2 = await test_client.get(f"/v1/versions/snapshots/{snapshot_id}")
    assert resp2.status_code == 404
