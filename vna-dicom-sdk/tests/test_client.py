"""Unit tests for DicomClient with mocked HTTP responses."""

import json
from unittest.mock import MagicMock, patch, PropertyMock

import httpx
import pytest

from dicom_sdk import DicomClient
from dicom_sdk.exceptions import (
    DicomAuthenticationError,
    DicomConnectionError,
    DicomNotFoundError,
    DicomServerError,
    DicomValidationError,
)
from dicom_sdk.models import (
    StudyMetadata,
    SeriesMetadata,
    InstanceMetadata,
    QueryResult,
    ServerStatistics,
    ModalityInfo,
)


@pytest.fixture
def client():
    """Create a test DicomClient."""
    c = DicomClient(base_url="http://localhost:8042", username="test", password="test")
    yield c
    c.close()


@pytest.fixture
def mock_response():
    """Create a mock httpx.Response."""
    def _make(status_code=200, json_data=None, content=b"", headers=None):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.is_success = 200 <= status_code < 300
        resp.json.return_value = json_data or {}
        resp.content = content
        resp.text = json.dumps(json_data) if json_data else ""
        resp.headers = headers or {"content-type": "application/json"}
        return resp
    return _make


class TestDicomClientInit:
    def test_init_default(self):
        c = DicomClient(base_url="http://localhost:8042")
        assert c.base_url == "http://localhost:8042"
        assert c.timeout == 30.0
        c.close()

    def test_init_trailing_slash(self):
        c = DicomClient(base_url="http://localhost:8042/")
        assert c.base_url == "http://localhost:8042"
        c.close()

    def test_context_manager(self):
        with DicomClient(base_url="http://localhost:8042") as c:
            assert c.base_url == "http://localhost:8042"

    def test_requests_use_relative_paths(self, client, mock_response):
        resp = mock_response(200, {"Version": "26.1.0"})
        with patch.object(client._client, "request", return_value=resp) as request:
            client.get_system()
            assert request.call_args.args[1] == "/system"


class TestStore:
    def test_store_success(self, client, mock_response, tmp_path):
        test_file = tmp_path / "test.dcm"
        test_file.write_bytes(b"\x00" * 132)
        result_data = {"SOPInstanceUID": "1.2.3", "StudyInstanceUID": "study-uid-123"}
        resp = mock_response(200, result_data)
        with patch.object(client._client, "request", return_value=resp):
            result = client.store(str(test_file))
            assert result.success is True
            assert result.sop_instance_uid == "1.2.3"

    def test_store_file_not_found(self, client):
        with pytest.raises(DicomValidationError, match="File not found"):
            client.store("/nonexistent/file.dcm")

    def test_upload_dicom(self, client, mock_response):
        result_data = {"SOPInstanceUID": "inst-123", "StudyInstanceUID": "study-456"}
        resp = mock_response(200, result_data)
        with patch.object(client._client, "request", return_value=resp):
            result = client.upload_dicom(b"\x00\x00DICM")
            assert result.success is True
            assert result.sop_instance_uid == "inst-123"


class TestQuery:
    def test_query_studies(self, client, mock_response):
        query_result = [{
            "StudyInstanceUID": "1.2.3.4",
            "StudyDate": "20240101",
            "StudyDescription": "Chest CT",
            "AccessionNumber": "ACC001",
            "PatientID": "P001",
            "PatientName": "DOE^JOHN",
        }]
        resp = mock_response(200, query_result)
        with patch.object(client._client, "request", return_value=resp):
            results = client.query(patient_id="P001")
            assert len(results) == 1
            assert results[0].patient_id == "P001"

    def test_query_empty(self, client, mock_response):
        resp = mock_response(200, [])
        with patch.object(client._client, "request", return_value=resp):
            results = client.query(patient_id="NONEXISTENT")
            assert results == []


class TestRetrieve:
    def test_retrieve_single(self, client, mock_response):
        dicom_bytes = b"\x00" * 132  # minimal DICOM-like bytes
        resp = mock_response(200, content=dicom_bytes, headers={"content-type": "application/dicom"})
        with patch.object(client._client, "request", return_value=resp):
            files = client.retrieve("study-uid-123")
            assert len(files) == 1
            assert files[0] == dicom_bytes

    def test_retrieve_with_output(self, client, mock_response, tmp_path):
        dicom_bytes = b"\x00" * 132
        resp = mock_response(200, content=dicom_bytes, headers={"content-type": "application/dicom"})
        with patch.object(client._client, "request", return_value=resp):
            out_dir = str(tmp_path / "output")
            files = client.retrieve("study-uid-123", output_dir=out_dir)
            assert len(files) == 1
            assert (tmp_path / "output" / "dicom_0000.dcm").exists()


class TestDelete:
    def test_delete_study(self, client, mock_response):
        find_resp = mock_response(200, ["orthanc-id-123"])
        delete_resp = mock_response(200, {})

        calls = []

        def mock_request(method, url, **kwargs):
            calls.append((method, url))
            if "tools/find" in url:
                return find_resp
            return delete_resp

        with patch.object(client._client, "request", side_effect=mock_request):
            result = client.delete("1.2.3.4")
            assert result is True


class TestMetadata:
    def test_get_study(self, client, mock_response):
        study_data = [{
            "StudyInstanceUID": "1.2.3.4",
            "StudyDate": "20240101",
            "StudyDescription": "Chest CT",
            "PatientID": "P001",
            "PatientName": "DOE^JOHN",
            "NumberOfStudyRelatedSeries": 2,
        }]
        study_resp = mock_response(200, study_data)
        with patch.object(client._client, "request", return_value=study_resp):
            study = client.get_study("1.2.3.4")
            assert study.study_instance_uid == "1.2.3.4"
            assert study.patient_id == "P001"

    def test_get_study_not_found(self, client, mock_response):
        empty_resp = mock_response(200, [])
        with patch.object(client._client, "request", return_value=empty_resp):
            with pytest.raises(DicomNotFoundError):
                client.get_study("nonexistent-uid")


class TestServerInfo:
    def test_get_statistics(self, client, mock_response):
        stats_data = {
            "CountStudies": 42,
            "CountSeries": 150,
            "CountInstances": 3000,
            "TotalDiskSize": 1073741824,
        }
        resp = mock_response(200, stats_data)
        with patch.object(client._client, "request", return_value=resp):
            stats = client.get_statistics()
            assert stats.count_studies == 42
            assert stats.count_series == 150
            assert stats.count_instances == 3000

    def test_list_modalities(self, client, mock_response):
        modalities_data = {
            "ORTHANC": {"AET": "ORTHANC", "Host": "127.0.0.1", "Port": 4242},
            "PACS": {"AET": "PACS1", "Host": "10.0.0.1", "Port": 104},
        }
        resp = mock_response(200, modalities_data)
        with patch.object(client._client, "request", return_value=resp):
            mods = client.list_modalities()
            assert len(mods) == 2
            assert mods[0].name == "ORTHANC"
            assert mods[0].aet == "ORTHANC"


class TestErrorHandling:
    def test_401_error(self, client, mock_response):
        resp = mock_response(401, {"message": "Unauthorized"})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(DicomAuthenticationError):
                client.get_statistics()

    def test_404_error(self, client, mock_response):
        resp = mock_response(404, {"message": "Not found"})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(DicomNotFoundError):
                client.get_statistics()

    def test_500_error(self, client, mock_response):
        resp = mock_response(500, {"message": "Internal error"})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(DicomServerError):
                client.get_statistics()

    def test_connection_error(self, client):
        with patch.object(
            client._client, "request",
            side_effect=httpx.ConnectError("Connection refused")
        ):
            with pytest.raises(DicomConnectionError, match="Failed to connect"):
                client.get_statistics()

    def test_timeout_error(self, client):
        with patch.object(
            client._client, "request",
            side_effect=httpx.TimeoutException("Timeout")
        ):
            with pytest.raises(DicomConnectionError, match="timed out"):
                client.get_statistics()


class TestRender:
    def test_render_png(self, client, mock_response):
        image_bytes = b"\x89PNG\r\n\x1a\n"
        render_resp = mock_response(200, content=image_bytes, headers={"content-type": "image/png"})
        with patch.object(client._client, "request", return_value=render_resp):
            data = client.render("study-uid", "series-uid", "sop-uid")
            assert data == image_bytes
