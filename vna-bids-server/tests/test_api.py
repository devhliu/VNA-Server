"""Tests for API endpoints."""
import io
import json
import pytest


@pytest.mark.asyncio
class TestHealthEndpoints:
    async def test_root(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "BIDS Server"
        assert data["protocol"] == "BIDSweb"

    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["live"] is True
        assert body["ready"] is True
        assert body["degraded"] is False


@pytest.mark.asyncio
class TestSubjectsAPI:
    async def test_create_subject(self, client):
        resp = await client.post("/api/subjects", json={
            "subject_id": "sub-001",
            "patient_ref": "pt-001",
            "hospital_ids": {"hospitalA": "P001"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "sub-001"
        assert data["patient_ref"] == "pt-001"

    async def test_create_duplicate_subject(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-001"})
        resp = await client.post("/api/subjects", json={"subject_id": "sub-001"})
        assert resp.status_code == 409

    async def test_get_subject(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-002"})
        resp = await client.get("/api/subjects/sub-002")
        assert resp.status_code == 200
        assert resp.json()["subject_id"] == "sub-002"

    async def test_get_nonexistent_subject(self, client):
        resp = await client.get("/api/subjects/sub-999")
        assert resp.status_code == 404

    async def test_list_subjects(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-003"})
        await client.post("/api/subjects", json={"subject_id": "sub-004"})
        resp = await client.get("/api/subjects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

    async def test_update_subject(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-005"})
        resp = await client.put("/api/subjects/sub-005", json={
            "patient_ref": "pt-updated",
        })
        assert resp.status_code == 200
        assert resp.json()["patient_ref"] == "pt-updated"

    async def test_delete_subject(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-006"})
        resp = await client.delete("/api/subjects/sub-006")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


@pytest.mark.asyncio
class TestSessionsAPI:
    async def test_create_session(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-010"})
        resp = await client.post("/api/sessions", json={
            "session_id": "sub-010_ses-001",
            "subject_id": "sub-010",
            "session_label": "ses-001",
        })
        assert resp.status_code == 201
        assert resp.json()["session_id"] == "sub-010_ses-001"

    async def test_list_sessions_by_subject(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-011"})
        await client.post("/api/sessions", json={
            "session_id": "sub-011_ses-001",
            "subject_id": "sub-011",
        })
        resp = await client.get("/api/sessions?subject_id=sub-011")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1


@pytest.mark.asyncio
class TestStoreAPI:
    async def test_upload_single_file(self, client):
        # Create subject first
        await client.post("/api/subjects", json={"subject_id": "sub-020"})
        await client.post("/api/sessions", json={
            "session_id": "sub-020_ses-001",
            "subject_id": "sub-020",
        })

        # Upload file
        file_content = b"test nifti data"
        resp = await client.post(
            "/api/store",
            data={
                "subject_id": "sub-020",
                "session_id": "sub-020_ses-001",
                "modality": "anat",
            },
            files={"file": ("sub-020_ses-001_T1w.nii.gz", file_content, "application/gzip")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_name"] == "sub-020_ses-001_T1w.nii.gz"
        assert data["modality"] == "anat"
        assert data["resource_id"].startswith("res-")
        assert data["file_size"] == len(file_content)

    async def test_upload_with_labels(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-021"})

        resp = await client.post(
            "/api/store",
            data={
                "subject_id": "sub-021",
                "modality": "anat",
                "labels": json.dumps({"diagnosis": "tumor", "qc": "pass"}),
            },
            files={"file": ("sub-021_T1w.nii.gz", b"data", "application/gzip")},
        )
        assert resp.status_code == 200

    async def test_chunked_upload_flow(self, client):
        # Init upload
        resp = await client.post("/api/store/init", json={
            "file_name": "large_file.nii.gz",
            "file_size": 100,
            "modality": "anat",
        })
        assert resp.status_code == 200
        data = resp.json()
        upload_id = data["upload_id"]
        assert upload_id.startswith("upl-")

        # Upload chunk
        resp = await client.patch(
            f"/api/store/{upload_id}",
            data={"chunk_index": "0"},
            files={"file": ("chunk", b"x" * 100, "application/octet-stream")},
        )
        assert resp.status_code == 200

        # Complete upload
        resp = await client.post(f"/api/store/{upload_id}/complete")
        assert resp.status_code == 200
        assert resp.json()["resource_id"].startswith("res-")

    async def test_chunked_upload_respects_requested_chunk_size(self, client):
        resp = await client.post("/api/store/init", json={
            "file_name": "large_file.nii.gz",
            "file_size": 100,
            "modality": "anat",
            "chunk_size": 50,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunk_size"] == 50
        assert data["total_chunks"] == 2


@pytest.mark.asyncio
class TestObjectsAPI:
    async def _create_resource(self, client, subject_id="sub-030", session_id=None):
        r1 = await client.post("/api/subjects", json={"subject_id": subject_id})
        assert r1.status_code == 201, f"Subject creation failed: {r1.status_code}"
        # Create session if specified
        if session_id:
            await client.post("/api/sessions", json={
                "session_id": session_id,
                "subject_id": subject_id,
            })
        data = {"subject_id": subject_id, "modality": "anat"}
        if session_id:
            data["session_id"] = session_id
        resp = await client.post(
            "/api/store",
            data=data,
            files={"file": ("test_T1w.nii.gz", b"test data content", "application/gzip")},
        )
        assert resp.status_code == 200, f"Upload failed: {resp.status_code} {resp.text[:200]}"
        return resp.json()["resource_id"]

    async def test_download_object(self, client):
        rid = await self._create_resource(client)
        resp = await client.get(f"/api/objects/{rid}")
        assert resp.status_code == 200, f"Download failed: {resp.status_code} rid={rid}"
        assert resp.content == b"test data content"

    async def test_get_metadata(self, client):
        rid = await self._create_resource(client)
        resp = await client.get(f"/api/objects/{rid}/metadata")
        assert resp.status_code == 200

    async def test_delete_object(self, client):
        rid = await self._create_resource(client, "sub-031")
        resp = await client.delete(f"/api/objects/{rid}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_get_nonexistent_object(self, client):
        resp = await client.get("/api/objects/res-nonexistent")
        assert resp.status_code == 404

    async def test_stream_with_range(self, client):
        rid = await self._create_resource(client, "sub-032")
        resp = await client.get(
            f"/api/objects/{rid}/stream",
            headers={"Range": "bytes=0-4"},
        )
        assert resp.status_code == 206
        assert resp.headers["content-range"].startswith("bytes 0-4/")


@pytest.mark.asyncio
class TestLabelsAPI:
    async def _create_resource(self, client, subject_id="sub-040"):
        await client.post("/api/subjects", json={"subject_id": subject_id})
        resp = await client.post(
            "/api/store",
            data={"subject_id": subject_id, "modality": "anat"},
            files={"file": ("test_T1w.nii.gz", b"data", "application/gzip")},
        )
        return resp.json()["resource_id"]

    async def test_set_labels(self, client):
        rid = await self._create_resource(client)
        resp = await client.put(f"/api/labels/{rid}", json={
            "labels": {"diagnosis": "tumor", "grade": "2"},
        })
        assert resp.status_code == 200
        labels = resp.json()
        assert len(labels) == 2

    async def test_patch_labels(self, client):
        rid = await self._create_resource(client, "sub-041")
        # Set initial
        await client.put(f"/api/labels/{rid}", json={
            "labels": {"a": "1", "b": "2"},
        })
        # Patch
        resp = await client.patch(f"/api/labels/{rid}", json={
            "add": {"c": "3"},
            "remove": ["a"],
        })
        assert resp.status_code == 200
        keys = {l["tag_key"] for l in resp.json()}
        assert "a" not in keys
        assert "c" in keys

    async def test_get_labels(self, client):
        rid = await self._create_resource(client, "sub-042")
        await client.put(f"/api/labels/{rid}", json={
            "labels": {"test": "value"},
        })
        resp = await client.get(f"/api/labels/{rid}")
        assert resp.status_code == 200
        # DB labels endpoint returns list of dicts with tag_key
        labels = resp.json()
        assert len(labels) >= 1

    async def test_list_all_tags(self, client):
        rid = await self._create_resource(client, "sub-043")
        await client.put(f"/api/labels/{rid}", json={
            "labels": {"diagnosis": "tumor"},
        })
        resp = await client.get("/api/labels")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
class TestAnnotationsAPI:
    async def _create_resource(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-050"})
        resp = await client.post(
            "/api/store",
            data={"subject_id": "sub-050", "modality": "anat"},
            files={"file": ("test.nii.gz", b"data", "application/gzip")},
        )
        return resp.json()["resource_id"]

    async def test_create_annotation(self, client):
        rid = await self._create_resource(client)
        resp = await client.post("/api/annotations", json={
            "resource_id": rid,
            "ann_type": "bbox",
            "label": "tumor",
            "data": {"x": 10, "y": 20, "w": 30, "h": 40},
            "confidence": 0.95,
            "created_by": "agent:seg",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["ann_type"] == "bbox"
        assert data["annotation_id"].startswith("ann-")

    async def test_list_annotations(self, client):
        rid = await self._create_resource(client)
        await client.post("/api/annotations", json={
            "resource_id": rid,
            "ann_type": "point",
            "data": {"x": 100, "y": 200},
        })
        resp = await client.get(f"/api/annotations?resource_id={rid}")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


@pytest.mark.asyncio
class TestQueryAPI:
    async def _setup_data(self, client):
        await client.post("/api/subjects", json={"subject_id": "sub-060"})
        await client.post(
            "/api/store",
            data={
                "subject_id": "sub-060",
                "modality": "anat",
                "labels": json.dumps({"diagnosis": "tumor"}),
            },
            files={"file": ("T1w.nii.gz", b"data1", "application/gzip")},
        )
        await client.post(
            "/api/store",
            data={
                "subject_id": "sub-060",
                "modality": "func",
                "labels": json.dumps({"qc": "pass"}),
            },
            files={"file": ("bold.nii.gz", b"data2", "application/gzip")},
        )

    async def test_query_by_subject(self, client):
        await self._setup_data(client)
        resp = await client.post("/api/query", json={
            "subject_id": "sub-060",
        })
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    async def test_query_by_modality(self, client):
        await self._setup_data(client)
        resp = await client.post("/api/query", json={
            "modality": ["anat"],
        })
        assert resp.status_code == 200
        for r in resp.json()["resources"]:
            assert r["modality"] == "anat"

    async def test_query_by_label(self, client):
        await self._setup_data(client)
        resp = await client.post("/api/query", json={
            "labels": {"match": ["tumor"]},
        })
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


@pytest.mark.asyncio
class TestModalitiesAPI:
    async def test_list_modalities(self, client):
        resp = await client.get("/api/modalities")
        assert resp.status_code == 200
        modalities = resp.json()
        assert len(modalities) > 0
        # Check default modalities loaded
        mod_ids = {m["modality_id"] for m in modalities}
        assert "anat" in mod_ids
        assert "func" in mod_ids

    async def test_register_custom_modality(self, client):
        resp = await client.post("/api/modalities", json={
            "modality_id": "custom_imaging",
            "directory": "custom_imaging",
            "description": "Custom imaging data",
            "extensions": [".nii.gz", ".custom"],
            "category": "imaging",
        })
        assert resp.status_code == 201
        assert resp.json()["modality_id"] == "custom_imaging"


@pytest.mark.asyncio
class TestVerifyAPI:
    async def test_verify_all(self, client):
        # Create some data
        await client.post("/api/subjects", json={"subject_id": "sub-070"})
        await client.post(
            "/api/store",
            data={"subject_id": "sub-070", "modality": "anat"},
            files={"file": ("test.nii.gz", b"data", "application/gzip")},
        )

        resp = await client.post("/api/verify", json={
            "target": "all",
            "check_hash": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_checked"] >= 1
        assert data["ok"] >= 1


@pytest.mark.asyncio
class TestRebuildAPI:
    async def test_rebuild_database(self, client):
        resp = await client.post("/api/rebuild", json={
            "target": "all",
            "clear_existing": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "subjects_found" in data
        assert "duration_seconds" in data


@pytest.mark.asyncio
class TestTasksAPI:
    async def test_create_task(self, client):
        resp = await client.post("/api/tasks", json={
            "action": "validate",
            "params": {"target": "all"},
        })
        assert resp.status_code == 202
        data = resp.json()
        assert data["task_id"].startswith("tsk-")
        assert data["status"] == "queued"

    async def test_get_task(self, client):
        resp = await client.post("/api/tasks", json={"action": "test"})
        task_id = resp.json()["task_id"]
        resp = await client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["task_id"] == task_id

    async def test_list_tasks(self, client):
        resp = await client.get("/api/tasks")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestWebhooksAPI:
    async def test_create_webhook(self, client):
        resp = await client.post("/api/webhooks", json={
            "name": "test-webhook",
            "url": "https://example.com/hook",
            "events": ["resource.created", "label.updated"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["webhook_id"].startswith("whk-")
        assert data["url"] == "https://example.com/hook"

    async def test_list_webhooks(self, client):
        resp = await client.get("/api/webhooks")
        assert resp.status_code == 200

    async def test_delete_webhook(self, client):
        resp = await client.post("/api/webhooks", json={
            "url": "https://example.com/hook2",
            "events": ["*"],
        })
        wh_id = resp.json()["webhook_id"]
        resp = await client.delete(f"/api/webhooks/{wh_id}")
        assert resp.status_code == 200
