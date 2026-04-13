"""Tests for unified query."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_query_all_resources(test_client: AsyncClient):
    await test_client.post("/v1/resources", json={
        "source_type": "dicom_only",
        "data_type": "dicom",
        "dicom_study_uid": "1.2.3",
    })

    resp = await test_client.post("/v1/query", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_query_by_source_type(test_client: AsyncClient):
    await test_client.post("/v1/resources", json={
        "source_type": "bids_only",
        "data_type": "nifti",
    })
    await test_client.post("/v1/resources", json={
        "source_type": "dicom_only",
        "data_type": "dicom",
    })

    resp = await test_client.post("/v1/query", json={"source_type": "bids_only"})
    data = resp.json()
    assert all(r["source_type"] == "bids_only" for r in data["items"])


@pytest.mark.asyncio
async def test_query_by_dicom_uid(test_client: AsyncClient):
    await test_client.post("/v1/resources", json={
        "source_type": "dicom_only",
        "data_type": "dicom",
        "dicom_study_uid": "1.2.3.4.5",
        "dicom_series_uid": "1.2.3.4.5.6",
    })

    resp = await test_client.post("/v1/query", json={"dicom_study_uid": "1.2.3.4.5"})
    data = resp.json()
    assert data["total"] >= 1
    assert all(r["dicom_study_uid"] == "1.2.3.4.5" for r in data["items"])


@pytest.mark.asyncio
async def test_query_by_bids_subject(test_client: AsyncClient):
    await test_client.post("/v1/resources", json={
        "source_type": "bids_only",
        "data_type": "nifti",
        "bids_subject_id": "sub-42",
        "bids_session_id": "ses-01",
    })

    resp = await test_client.post("/v1/query", json={"bids_subject_id": "sub-42"})
    data = resp.json()
    assert data["total"] >= 1
    assert all(r["bids_subject_id"] == "sub-42" for r in data["items"])


@pytest.mark.asyncio
async def test_query_by_labels(test_client: AsyncClient):
    resp = await test_client.post("/v1/resources", json={
        "source_type": "dicom_only",
        "data_type": "dicom",
    })
    rid = resp.json()["resource_id"]
    await test_client.put(f"/v1/labels/resource/{rid}", json={
        "labels": [
            {"tag_key": "modality", "tag_value": "CT"},
            {"tag_key": "region", "tag_value": "chest"},
        ],
    })

    # Query by label
    resp = await test_client.post("/v1/query", json={
        "labels": [{"tag_key": "modality", "tag_value": "CT"}],
    })
    data = resp.json()
    assert data["total"] >= 1

    # Query by multiple labels (AND)
    resp = await test_client.post("/v1/query", json={
        "labels": [
            {"tag_key": "modality", "tag_value": "CT"},
            {"tag_key": "region", "tag_value": "chest"},
        ],
    })
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_query_text_search(test_client: AsyncClient):
    await test_client.post("/v1/resources", json={
        "source_type": "dicom_only",
        "data_type": "dicom",
        "file_name": "chest_ct_scan_2024.dcm",
    })

    resp = await test_client.post("/v1/query", json={"text_search": "chest"})
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_query_by_hospital_id(test_client: AsyncClient):
    # Create patient
    await test_client.post("/v1/patients", json={
        "patient_ref": "pt-hosp-query",
        "hospital_id": "H-QUERY-999",
        "source": "hospitalA",
    })
    # Create resource linked to patient
    await test_client.post("/v1/resources", json={
        "patient_ref": "pt-hosp-query",
        "source_type": "dicom_only",
        "data_type": "dicom",
    })

    resp = await test_client.post("/v1/query", json={"hospital_id": "H-QUERY-999"})
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_query_pagination(test_client: AsyncClient):
    for i in range(10):
        await test_client.post("/v1/resources", json={
            "source_type": "dicom_only",
            "data_type": "dicom",
            "file_name": f"page_test_{i}.dcm",
        })

    resp = await test_client.post("/v1/query", json={"offset": 0, "limit": 5})
    data = resp.json()
    assert len(data["items"]) == 5
    assert data["total"] >= 10
