"""Unit tests for BidsClient with mocked HTTP responses."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from bids_sdk import BidsClient, AsyncBidsClient
from bids_sdk.exceptions import (
    BidsAuthenticationError,
    BidsConnectionError,
    BidsHTTPError,
    BidsNotFoundError,
    BidsServerError,
    BidsTimeoutError,
    BidsValidationError,
)
from bids_sdk.models import Resource, Subject, Session, Task, Webhook, Modality, QueryResult

BASE_URL = "http://test-server:8080"


@pytest.fixture
def client():
    """Create a test client."""
    c = BidsClient(base_url=BASE_URL, timeout=5.0)
    yield c
    c.close()


@pytest.fixture
def tmp_file():
    """Create a temporary file for upload tests."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nii.gz", delete=False) as f:
        f.write("fake nifti data" * 1000)
        f.flush()
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


# ------------------------------------------------------------------
# Connection and error handling
# ------------------------------------------------------------------

class TestClientBasics:
    def test_client_init(self):
        c = BidsClient(base_url=BASE_URL, timeout=10.0)
        assert c.base_url == BASE_URL
        assert c.timeout == 10.0
        c.close()

    def test_client_trailing_slash(self):
        c = BidsClient(base_url="http://example.com/")
        assert c.base_url == "http://example.com"
        c.close()

    def test_context_manager(self):
        with BidsClient(base_url=BASE_URL) as c:
            assert c is not None

    def test_api_key_header(self):
        c = BidsClient(base_url=BASE_URL, api_key="test-key-123")
        assert "Authorization" in c._client.headers
        assert c._client.headers["Authorization"] == "Bearer test-key-123"
        c.close()


class TestErrorHandling:
    @respx.mock
    def test_401_error(self, client):
        respx.get(f"{BASE_URL}/api/subjects").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(BidsAuthenticationError):
            client.list_subjects()

    @respx.mock
    def test_404_error(self, client):
        respx.get(f"{BASE_URL}/api/subjects/missing").mock(
            return_value=httpx.Response(404, json={"message": "Subject not found"})
        )
        with pytest.raises(BidsNotFoundError):
            client.get_subject("missing")

    @respx.mock
    def test_500_error(self, client):
        respx.get(f"{BASE_URL}/api/subjects").mock(
            return_value=httpx.Response(500, json={"error": "Internal Server Error"})
        )
        with pytest.raises(BidsServerError):
            client.list_subjects()

    @respx.mock
    def test_400_error(self, client):
        respx.post(f"{BASE_URL}/api/subjects").mock(
            return_value=httpx.Response(400, json={"message": "Bad request"})
        )
        with pytest.raises(BidsValidationError):
            client.create_subject("sub-01")

    @respx.mock
    def test_timeout_error(self, client):
        respx.get(f"{BASE_URL}/api/subjects").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        with pytest.raises(BidsTimeoutError):
            client.list_subjects()

    @respx.mock
    def test_connection_error(self, client):
        respx.get(f"{BASE_URL}/api/subjects").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        with pytest.raises(BidsConnectionError):
            client.list_subjects()


# ------------------------------------------------------------------
# Subject endpoints
# ------------------------------------------------------------------

class TestSubjects:
    @respx.mock
    def test_create_subject(self, client):
        respx.post(f"{BASE_URL}/api/subjects").mock(
            return_value=httpx.Response(
                200,
                json={"subject_id": "sub-01", "patient_ref": "P001", "hospital_ids": {"0": "H1"}},
            )
        )
        subject = client.create_subject("sub-01", patient_ref="P001", hospital_ids=["H1"])
        assert subject.subject_id == "sub-01"
        assert subject.patient_ref == "P001"
        assert subject.hospital_ids == {"0": "H1"}

    @respx.mock
    def test_get_subject(self, client):
        respx.get(f"{BASE_URL}/api/subjects/sub-01").mock(
            return_value=httpx.Response(
                200, json={"subject_id": "sub-01", "patient_ref": "P001"}
            )
        )
        subject = client.get_subject("sub-01")
        assert subject.subject_id == "sub-01"

    @respx.mock
    def test_list_subjects(self, client):
        respx.get(f"{BASE_URL}/api/subjects").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"subject_id": "sub-01"},
                    {"subject_id": "sub-02"},
                ],
            )
        )
        subjects = client.list_subjects()
        assert len(subjects) == 2
        assert subjects[0].subject_id == "sub-01"


# ------------------------------------------------------------------
# Session endpoints
# ------------------------------------------------------------------

class TestSessions:
    @respx.mock
    def test_create_session(self, client):
        respx.post(f"{BASE_URL}/api/sessions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "session_id": "ses-01",
                    "subject_id": "sub-01",
                    "session_label": "baseline",
                },
            )
        )
        session = client.create_session("ses-01", "sub-01", session_label="baseline")
        assert session.session_id == "ses-01"
        assert session.session_label == "baseline"

    @respx.mock
    def test_list_sessions(self, client):
        respx.get(f"{BASE_URL}/api/sessions").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"session_id": "ses-01", "subject_id": "sub-01"},
                    {"session_id": "ses-02", "subject_id": "sub-01"},
                ],
            )
        )
        sessions = client.list_sessions()
        assert len(sessions) == 2

    @respx.mock
    def test_list_sessions_filtered(self, client):
        route = respx.get(f"{BASE_URL}/api/sessions").mock(
            return_value=httpx.Response(200, json=[{"session_id": "ses-01", "subject_id": "sub-01"}])
        )
        client.list_sessions(subject_id="sub-01")
        assert route.called
        assert route.calls[0].request.url.params["subject_id"] == "sub-01"


# ------------------------------------------------------------------
# Query endpoints
# ------------------------------------------------------------------

class TestQuery:
    @respx.mock
    def test_query_all(self, client):
        respx.post(f"{BASE_URL}/api/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resources": [
                        {"resource_id": "res-01", "file_name": "T1w.nii.gz"},
                    ],
                    "total": 1,
                },
            )
        )
        result = client.query()
        assert result.total == 1
        assert len(result.resources) == 1
        assert result.resources[0].file_name == "T1w.nii.gz"

    @respx.mock
    def test_query_with_filters(self, client):
        route = respx.post(f"{BASE_URL}/api/query").mock(
            return_value=httpx.Response(200, json={"resources": [], "total": 0})
        )
        client.query(subject_id="sub-01", modality="anat", limit=10, offset=0)
        body = json.loads(route.calls[0].request.content)
        assert body["subject_id"] == "sub-01"
        assert body["modality"] == ["anat"]
        assert body["limit"] == 10

    @respx.mock
    def test_query_with_labels(self, client):
        route = respx.post(f"{BASE_URL}/api/query").mock(
            return_value=httpx.Response(200, json={"resources": [], "total": 0})
        )
        client.query(labels=["tag1", "tag2"])
        body = json.loads(route.calls[0].request.content)
        assert body["labels"] == {"match": ["tag1", "tag2"]}


# ------------------------------------------------------------------
# Label endpoints
# ------------------------------------------------------------------

class TestLabels:
    @respx.mock
    def test_get_labels(self, client):
        respx.get(f"{BASE_URL}/api/labels/res-01").mock(
            return_value=httpx.Response(
                200, json=[{"tag_key": "quality", "tag_value": "good"}]
            )
        )
        labels = client.get_labels("res-01")
        assert len(labels) == 1
        assert labels[0]["key"] == "quality"

    @respx.mock
    def test_set_labels(self, client):
        route = respx.put(f"{BASE_URL}/api/labels/res-01").mock(
            return_value=httpx.Response(
                200, json=[{"tag_key": "new-tag", "tag_value": True}]
            )
        )
        labels = client.set_labels("res-01", ["new-tag"])
        assert len(labels) == 1
        assert json.loads(route.calls[0].request.content) == {"labels": {"new-tag": True}}

    @respx.mock
    def test_patch_labels(self, client):
        route = respx.patch(f"{BASE_URL}/api/labels/res-01").mock(
            return_value=httpx.Response(
                200, json=[{"tag_key": "added", "tag_value": True}, {"tag_key": "existing", "tag_value": True}]
            )
        )
        labels = client.patch_labels("res-01", add=["added"], remove=["old"])
        assert len(labels) == 2
        assert json.loads(route.calls[0].request.content) == {
            "add": {"added": True},
            "remove": ["old"],
        }

    @respx.mock
    def test_list_all_tags(self, client):
        respx.get(f"{BASE_URL}/api/labels").mock(
            return_value=httpx.Response(
                200, json=[{"key": "quality", "count": 42}]
            )
        )
        tags = client.list_all_tags()
        assert len(tags) == 1
        assert tags[0]["count"] == 42


# ------------------------------------------------------------------
# Annotation endpoints
# ------------------------------------------------------------------

class TestAnnotations:
    @respx.mock
    def test_create_annotation(self, client):
        respx.post(f"{BASE_URL}/api/annotations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "annotation_id": "ann-01",
                    "resource_id": "res-01",
                    "ann_type": "region",
                    "label": "hippocampus",
                    "data": {},
                    "confidence": 0.95,
                },
            )
        )
        ann = client.create_annotation("res-01", "region", "hippocampus", confidence=0.95)
        assert ann.label == "hippocampus"
        assert ann.confidence == 0.95

    @respx.mock
    def test_list_annotations(self, client):
        respx.get(f"{BASE_URL}/api/objects/res-01/annotations").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"annotation_id": "ann-01", "resource_id": "res-01", "ann_type": "region", "label": "hippocampus", "data": {}},
                    {"annotation_id": "ann-02", "resource_id": "res-01", "ann_type": "artifact", "label": "motion", "data": {}},
                ],
            )
        )
        anns = client.list_annotations("res-01")
        assert len(anns) == 2


# ------------------------------------------------------------------
# Task endpoints
# ------------------------------------------------------------------

class TestTasks:
    @respx.mock
    def test_submit_task(self, client):
        respx.post(f"{BASE_URL}/api/tasks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "task_id": "task-01",
                    "action": "convert",
                    "status": "pending",
                    "resource_ids": ["res-01"],
                },
            )
        )
        task = client.submit_task("convert", ["res-01"])
        assert task.task_id == "task-01"
        assert task.status == "pending"

    @respx.mock
    def test_get_task(self, client):
        respx.get(f"{BASE_URL}/api/tasks/task-01").mock(
            return_value=httpx.Response(
                200,
                json={"task_id": "task-01", "action": "convert", "status": "completed", "progress": 1.0},
            )
        )
        task = client.get_task("task-01")
        assert task.status == "completed"
        assert task.progress == 1.0

    @respx.mock
    def test_cancel_task(self, client):
        respx.delete(f"{BASE_URL}/api/tasks/task-01").mock(
            return_value=httpx.Response(
                200,
                json={"cancelled": True, "task_id": "task-01"},
            )
        )
        task = client.cancel_task("task-01")
        assert task["cancelled"] is True


# ------------------------------------------------------------------
# Webhook endpoints
# ------------------------------------------------------------------

class TestWebhooks:
    @respx.mock
    def test_create_webhook(self, client):
        respx.post(f"{BASE_URL}/api/webhooks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "webhook_id": "wh-01",
                    "url": "https://example.com/hook",
                    "events": ["upload", "delete"],
                    "name": "test-hook",
                },
            )
        )
        wh = client.create_webhook("https://example.com/hook", ["upload", "delete"], name="test-hook")
        assert wh.webhook_id == "wh-01"
        assert wh.name == "test-hook"

    @respx.mock
    def test_list_webhooks(self, client):
        respx.get(f"{BASE_URL}/api/webhooks").mock(
            return_value=httpx.Response(
                200,
                json=[{"webhook_id": "wh-01", "url": "https://example.com", "events": ["upload"]}],
            )
        )
        whs = client.list_webhooks()
        assert len(whs) == 1

    @respx.mock
    def test_delete_webhook(self, client):
        respx.delete(f"{BASE_URL}/api/webhooks/wh-01").mock(
            return_value=httpx.Response(204)
        )
        client.delete_webhook("wh-01")


# ------------------------------------------------------------------
# System endpoints
# ------------------------------------------------------------------

class TestSystem:
    @respx.mock
    def test_verify(self, client):
        respx.post(f"{BASE_URL}/api/verify").mock(
            return_value=httpx.Response(
                200,
                json={"status": "ok", "checked": 100, "errors": []},
            )
        )
        result = client.verify(check_hash=True)
        assert result["status"] == "ok"
        assert result["checked"] == 100

    @respx.mock
    def test_rebuild(self, client):
        respx.post(f"{BASE_URL}/api/rebuild").mock(
            return_value=httpx.Response(
                200,
                json={"status": "started", "task_id": "task-rebuild-01"},
            )
        )
        result = client.rebuild(clear_existing=False)
        assert result["status"] == "started"

    @respx.mock
    def test_list_modalities(self, client):
        respx.get(f"{BASE_URL}/api/modalities").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"modality_id": "anat", "directory": "anat", "extensions": [".nii.gz"]},
                    {"modality_id": "func", "directory": "func", "extensions": [".nii.gz", ".json"]},
                ],
            )
        )
        modalities = client.list_modalities()
        assert len(modalities) == 2
        assert modalities[0].modality_id == "anat"

    @respx.mock
    def test_register_modality(self, client):
        respx.post(f"{BASE_URL}/api/modalities").mock(
            return_value=httpx.Response(
                200,
                json={"modality_id": "pet", "directory": "pet", "extensions": [".nii.gz"]},
            )
        )
        mod = client.register_modality("pet", "pet", [".nii.gz"])
        assert mod.modality_id == "pet"


# ------------------------------------------------------------------
# Upload / Download
# ------------------------------------------------------------------

class TestUploadDownload:
    @respx.mock
    def test_upload(self, client, tmp_file):
        respx.post(f"{BASE_URL}/api/store").mock(
            return_value=httpx.Response(
                200,
                json={"resource_id": "res-01", "file_name": tmp_file.name},
            )
        )
        result = client.upload(
            tmp_file,
            subject_id="sub-01",
            session_id="ses-01",
            modality="anat",
        )
        assert result.resource_id == "res-01"

    @respx.mock
    def test_upload_with_labels(self, client, tmp_file):
        route = respx.post(f"{BASE_URL}/api/store").mock(
            return_value=httpx.Response(200, json={"resource_id": "res-01"})
        )
        client.upload(
            tmp_file,
            subject_id="sub-01",
            session_id="ses-01",
            modality="anat",
            labels=["test", "quality:good"],
            metadata={"project": "pilot"},
        )
        assert route.called
        body = route.calls[0].request.content.decode("utf-8", errors="ignore")
        assert '"labels"' in body
        assert '"test": true' in body
        assert '"quality": "good"' in body
        assert '"project": "pilot"' in body

    def test_upload_file_not_found(self, client):
        with pytest.raises(BidsValidationError, match="File not found"):
            client.upload(
                "/nonexistent/file.nii.gz",
                subject_id="sub-01",
                session_id="ses-01",
                modality="anat",
            )

    @respx.mock
    def test_download(self, client, tmp_file):
        output = tmp_file.parent / "downloaded.nii.gz"
        respx.get(f"{BASE_URL}/api/objects/res-01/stream").mock(
            return_value=httpx.Response(200, content=b"downloaded data")
        )
        result = client.download("res-01", output)
        assert result.exists()
        assert result.read_bytes() == b"downloaded data"
        result.unlink()

    @respx.mock
    def test_download_stream_with_range(self, client, tmp_file):
        output = tmp_file.parent / "range_download.nii.gz"
        respx.get(f"{BASE_URL}/api/objects/res-01/stream").mock(
            return_value=httpx.Response(206, content=b"partial data")
        )
        result = client.download_stream("res-01", output, range_start=0, range_end=100)
        assert result.exists()
        result.unlink()

    @respx.mock
    def test_batch_download(self, client, tmp_file):
        output = tmp_file.parent / "batch.zip"
        respx.post(f"{BASE_URL}/api/objects/batch-download").mock(
            return_value=httpx.Response(200, content=b"zip data")
        )
        result = client.batch_download(["res-01", "res-02"], output)
        assert result.exists()
        result.unlink()


# ------------------------------------------------------------------
# Progress callback
# ------------------------------------------------------------------

class TestProgressCallback:
    @respx.mock
    def test_upload_progress_callback(self, client, tmp_file):
        respx.post(f"{BASE_URL}/api/store").mock(
            return_value=httpx.Response(200, json={"resource_id": "res-01"})
        )
        progress_calls = []

        def callback(bytes_read, total):
            progress_calls.append((bytes_read, total))

        client.upload(
            tmp_file,
            subject_id="sub-01",
            session_id="ses-01",
            modality="anat",
            progress_callback=callback,
        )
        assert len(progress_calls) > 0

    @respx.mock
    def test_download_progress_callback(self, client, tmp_file):
        output = tmp_file.parent / "progress_dl.nii.gz"
        respx.get(f"{BASE_URL}/api/objects/res-01/stream").mock(
            return_value=httpx.Response(200, content=b"data" * 100, headers={"content-length": "400"})
        )
        progress_calls = []

        def callback(written, total):
            progress_calls.append((written, total))

        client.download("res-01", output, progress_callback=callback)
        assert len(progress_calls) > 0
        output.unlink()


# ------------------------------------------------------------------
# Async client
# ------------------------------------------------------------------

class TestAsyncClient:
    @pytest.mark.asyncio
    async def test_async_init(self):
        c = AsyncBidsClient(base_url=BASE_URL)
        assert c.base_url == BASE_URL
        await c.close()

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            assert c is not None

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_list_subjects(self):
        respx.get(f"{BASE_URL}/api/subjects").mock(
            return_value=httpx.Response(200, json=[{"subject_id": "sub-01"}])
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            subjects = await c.list_subjects()
            assert len(subjects) == 1
            assert subjects[0].subject_id == "sub-01"

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_create_subject(self):
        respx.post(f"{BASE_URL}/api/subjects").mock(
            return_value=httpx.Response(200, json={"subject_id": "sub-02"})
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            subject = await c.create_subject("sub-02")
            assert subject.subject_id == "sub-02"

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_query(self):
        respx.post(f"{BASE_URL}/api/query").mock(
            return_value=httpx.Response(200, json={"resources": [{"resource_id": "r1"}], "total": 1})
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            result = await c.query(subject_id="sub-01")
            assert result.total == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_create_annotation(self):
        respx.post(f"{BASE_URL}/api/annotations").mock(
            return_value=httpx.Response(
                200,
                json={"annotation_id": "ann-01", "resource_id": "r1", "ann_type": "note", "label": "test", "data": {}},
            )
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            ann = await c.create_annotation("r1", "note", "test")
            assert ann.label == "test"

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_submit_task(self):
        respx.post(f"{BASE_URL}/api/tasks").mock(
            return_value=httpx.Response(
                200,
                json={"task_id": "t1", "action": "convert", "status": "pending", "resource_ids": ["r1"]},
            )
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            task = await c.submit_task("convert", ["r1"])
            assert task.task_id == "t1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_webhooks(self):
        respx.post(f"{BASE_URL}/api/webhooks").mock(
            return_value=httpx.Response(
                200,
                json={"webhook_id": "wh1", "url": "https://example.com", "events": ["upload"]},
            )
        )
        respx.get(f"{BASE_URL}/api/webhooks").mock(
            return_value=httpx.Response(
                200,
                json=[{"webhook_id": "wh1", "url": "https://example.com", "events": ["upload"]}],
            )
        )
        respx.delete(f"{BASE_URL}/api/webhooks/wh1").mock(
            return_value=httpx.Response(204)
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            wh = await c.create_webhook("https://example.com", ["upload"])
            assert wh.webhook_id == "wh1"
            whs = await c.list_webhooks()
            assert len(whs) == 1
            await c.delete_webhook("wh1")

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_system(self):
        respx.post(f"{BASE_URL}/api/verify").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.post(f"{BASE_URL}/api/rebuild").mock(
            return_value=httpx.Response(200, json={"status": "started"})
        )
        respx.get(f"{BASE_URL}/api/modalities").mock(
            return_value=httpx.Response(200, json=[{"modality_id": "anat"}])
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            result = await c.verify()
            assert result["status"] == "ok"
            result = await c.rebuild()
            assert result["status"] == "started"
            mods = await c.list_modalities()
            assert len(mods) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_labels(self):
        respx.get(f"{BASE_URL}/api/labels/r1").mock(
            return_value=httpx.Response(200, json=[{"tag_key": "tag1", "tag_value": True}])
        )
        respx.put(f"{BASE_URL}/api/labels/r1").mock(
            return_value=httpx.Response(200, json=[{"tag_key": "new-tag", "tag_value": True}])
        )
        respx.patch(f"{BASE_URL}/api/labels/r1").mock(
            return_value=httpx.Response(200, json=[{"tag_key": "added", "tag_value": True}])
        )
        respx.get(f"{BASE_URL}/api/labels").mock(
            return_value=httpx.Response(200, json=[{"key": "tag1", "count": 5}])
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            labels = await c.get_labels("r1")
            assert len(labels) == 1
            labels = await c.set_labels("r1", ["new-tag"])
            assert labels[0]["key"] == "new-tag"
            labels = await c.patch_labels("r1", add=["added"])
            assert labels[0]["key"] == "added"
            tags = await c.list_all_tags()
            assert tags[0]["count"] == 5
        assert respx.calls.call_count == 4
        assert json.loads(respx.calls[1].request.content) == {"labels": {"new-tag": True}}
        assert json.loads(respx.calls[2].request.content) == {"add": {"added": True}}

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_sessions(self):
        respx.post(f"{BASE_URL}/api/sessions").mock(
            return_value=httpx.Response(
                200, json={"session_id": "ses-01", "subject_id": "sub-01"}
            )
        )
        respx.get(f"{BASE_URL}/api/sessions").mock(
            return_value=httpx.Response(
                200, json=[{"session_id": "ses-01", "subject_id": "sub-01"}]
            )
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            session = await c.create_session("ses-01", "sub-01")
            assert session.session_id == "ses-01"
            sessions = await c.list_sessions()
            assert len(sessions) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_tasks(self):
        respx.get(f"{BASE_URL}/api/tasks/t1").mock(
            return_value=httpx.Response(
                200, json={"task_id": "t1", "action": "convert", "status": "running"}
            )
        )
        respx.delete(f"{BASE_URL}/api/tasks/t1").mock(
            return_value=httpx.Response(
                200, json={"cancelled": True, "task_id": "t1"}
            )
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            task = await c.get_task("t1")
            assert task.status == "running"
            task = await c.cancel_task("t1")
            assert task["cancelled"] is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_annotations(self):
        respx.get(f"{BASE_URL}/api/objects/r1/annotations").mock(
            return_value=httpx.Response(
                200,
                json=[{"annotation_id": "a1", "resource_id": "r1", "ann_type": "note", "label": "good", "data": {}}],
            )
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            anns = await c.list_annotations("r1")
            assert len(anns) == 1
            assert anns[0].label == "good"

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_register_modality(self):
        respx.post(f"{BASE_URL}/api/modalities").mock(
            return_value=httpx.Response(
                200, json={"modality_id": "pet", "directory": "pet", "extensions": [".nii.gz"]}
            )
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            mod = await c.register_modality("pet", "pet", [".nii.gz"])
            assert mod.modality_id == "pet"

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_download(self, tmp_file):
        output = tmp_file.parent / "async_dl.nii.gz"
        respx.get(f"{BASE_URL}/api/objects/r1/stream").mock(
            return_value=httpx.Response(200, content=b"async data")
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            result = await c.download("r1", output)
            assert result.exists()
            assert result.read_bytes() == b"async data"
            result.unlink()

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_batch_download(self, tmp_file):
        output = tmp_file.parent / "async_batch.zip"
        respx.post(f"{BASE_URL}/api/objects/batch-download").mock(
            return_value=httpx.Response(200, content=b"zip data")
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            result = await c.batch_download(["r1", "r2"], output)
            assert result.exists()
            result.unlink()

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        respx.get(f"{BASE_URL}/api/subjects").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        async with AsyncBidsClient(base_url=BASE_URL) as c:
            with pytest.raises(BidsNotFoundError):
                await c.list_subjects()
