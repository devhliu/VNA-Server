"""Tests for project management API."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(test_client: AsyncClient):
    resp = await test_client.post("/v1/projects", json={
        "name": "Test Project",
        "description": "A test research project",
        "principal_investigator": "Dr. Smith",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Project"
    assert data["project_id"].startswith("prj-")


@pytest.mark.asyncio
async def test_list_projects(test_client: AsyncClient):
    await test_client.post("/v1/projects", json={"name": "Project 1"})
    await test_client.post("/v1/projects", json={"name": "Project 2"})

    resp = await test_client.get("/v1/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_get_project(test_client: AsyncClient):
    create_resp = await test_client.post("/v1/projects", json={"name": "Get Test"})
    project_id = create_resp.json()["project_id"]

    resp = await test_client.get(f"/v1/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Test"


@pytest.mark.asyncio
async def test_get_project_not_found(test_client: AsyncClient):
    resp = await test_client.get("/v1/projects/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_project(test_client: AsyncClient):
    create_resp = await test_client.post("/v1/projects", json={"name": "Before Update"})
    project_id = create_resp.json()["project_id"]

    resp = await test_client.put(f"/v1/projects/{project_id}", json={"name": "After Update"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "After Update"


@pytest.mark.asyncio
async def test_delete_project(test_client: AsyncClient):
    create_resp = await test_client.post("/v1/projects", json={"name": "Delete Me"})
    project_id = create_resp.json()["project_id"]

    resp = await test_client.delete(f"/v1/projects/{project_id}")
    assert resp.status_code == 204

    resp = await test_client.get(f"/v1/projects/{project_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_project_members(test_client: AsyncClient):
    # Create patient first
    await test_client.post("/v1/patients", json={
        "patient_ref": "pt-member-test",
        "hospital_id": "H001",
        "source": "hospitalA",
    })

    create_resp = await test_client.post("/v1/projects", json={"name": "Member Project"})
    project_id = create_resp.json()["project_id"]

    # Add member
    resp = await test_client.post(f"/v1/projects/{project_id}/members", json={
        "patient_ref": "pt-member-test",
        "role": "PI",
    })
    assert resp.status_code == 201
    assert resp.json()["role"] == "PI"

    # List members
    resp = await test_client.get(f"/v1/projects/{project_id}/members")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_project_resources(test_client: AsyncClient):
    # Create a resource first
    res_resp = await test_client.post("/v1/resources", json={
        "data_type": "dicom",
        "source_type": "dicom_only",
        "file_name": "project_res.dcm",
    })
    resource_id = res_resp.json()["resource_id"]

    create_resp = await test_client.post("/v1/projects", json={"name": "Resource Project"})
    project_id = create_resp.json()["project_id"]

    # Add resource
    resp = await test_client.post(f"/v1/projects/{project_id}/resources", json={
        "resource_id": resource_id,
    })
    assert resp.status_code == 201

    # List resources
    resp = await test_client.get(f"/v1/projects/{project_id}/resources")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
