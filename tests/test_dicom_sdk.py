"""Integration tests for DICOM SDK - client-to-server communication with mocked Orthanc."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from dicom_sdk import DicomClient, AsyncDicomClient
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
    PatientMetadata,
)


def make_mock_response(
    status_code: int = 200,
    json_data: Any = None,
    content: bytes = b"",
    headers: dict | None = None,
) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    resp.content = content
    resp.text = json.dumps(json_data) if json_data else ""
    resp.headers = headers or {"content-type": "application/json"}
    return resp


@pytest.fixture
def sync_client():
    client = DicomClient(base_url="http://localhost:8042", username="orthanc", password="orthanc")
    yield client
    client.close()


@pytest.fixture
def mock_orthanc_patient():
    return {
        "ID": "P001",
        "PatientID": "P001",
        "PatientName": "Test^Patient",
        "PatientBirthDate": "19900101",
        "PatientSex": "M",
        "PatientAge": "034Y",
        "IsProtected": False,
        "Studies": ["1.2.3.4.5"],
        "MainDicomTags": {
            "PatientID": "P001",
            "PatientName": "Test^Patient",
            "PatientBirthDate": "19900101",
            "PatientSex": "M",
        },
    }


@pytest.fixture
def mock_orthanc_study():
    return {
        "ID": "1.2.3.4.5",
        "ParentPatient": "P001",
        "StudyInstanceUID": "1.2.3.4.5",
        "StudyDate": "20240101",
        "StudyDescription": "CT Chest",
        "ModalitiesInStudy": ["CT", "DX"],
        "MainDicomTags": {
            "StudyInstanceUID": "1.2.3.4.5",
            "StudyDate": "20240101",
            "StudyDescription": "CT Chest",
            "ModalitiesInStudy": ["CT", "DX"],
        },
        "Series": ["1.2.3.4.5.1"],
        "TotalInstances": 120,
    }


@pytest.fixture
def mock_orthanc_series():
    return {
        "ID": "1.2.3.4.5.1",
        "ParentStudy": "1.2.3.4.5",
        "SeriesInstanceUID": "1.2.3.4.5.1",
        "SeriesDescription": "CT Chest 5mm",
        "Modality": "CT",
        "SeriesNumber": "1",
        "MainDicomTags": {
            "SeriesInstanceUID": "1.2.3.4.5.1",
            "SeriesDescription": "CT Chest 5mm",
            "Modality": "CT",
        },
        "Instances": ["1.2.3.4.5.1.1"],
        "ExpectedNumberOfInstances": 120,
    }


@pytest.fixture
def mock_orthanc_instance():
    return {
        "ID": "1.2.3.4.5.1.1",
        "ParentSeries": "1.2.3.4.5.1",
        "SOPInstanceUID": "1.2.3.4.5.1.1",
        "InstanceNumber": "1",
        "MainDicomTags": {
            "SOPInstanceUID": "1.2.3.4.5.1.1",
            "InstanceNumber": "1",
        },
    }


@pytest.fixture
def mock_system_info():
    return {
        "Version": "26.1.0",
        "ApiVersion": "4",
        "Database": "PostgreSQL",
        "Name": "Orthanc",
        "StorageArea": "File",
        "RegisteredUsers": {"orthanc": "orthanc"},
    }


@pytest.fixture
def mock_statistics():
    return {
        "CountStudies": 42,
        "CountSeries": 128,
        "CountInstances": 3840,
        "TotalDiskSize": 42_000_000_000,
        "TotalDiskSizeUnit": "bytes",
    }


@pytest.fixture
def mock_changes():
    return {
        "content": [
            {"Seq": 1, "Path": "/studies/1.2.3.4.5", "ResourceType": "Study", "Type": "IsNew"},
            {"Seq": 2, "Path": "/studies/1.2.3.4.5.1", "ResourceType": "Series", "Type": "IsNew"},
        ],
        "last": 2,
        "state": "2024-01-01T00:00:00Z",
    }


# =============================================================================
# Init Tests
# =============================================================================

class TestDicomClientInit:
    def test_base_url_normalization(self):
        c = DicomClient("http://localhost:8042/")
        assert c.base_url == "http://localhost:8042"
        c.close()

    def test_context_manager(self):
        with DicomClient("http://localhost:8042") as c:
            assert c.base_url == "http://localhost:8042"

    def test_custom_timeout(self):
        c = DicomClient("http://localhost:8042", timeout=60.0)
        assert c.timeout == 60.0
        c.close()


# =============================================================================
# Store Tests
# =============================================================================

class TestStoreOperations:
    def test_store_success(self, sync_client, mock_orthanc_study, tmp_path: Path):
        test_file = tmp_path / "test.dcm"
        test_file.write_bytes(b"\x00" * 256)

        mock_resp = make_mock_response(200, {"ID": "1.2.3.4.5.1.1", "ParentStudy": "1.2.3.4.5"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.store(str(test_file))
            assert result.success is True
            assert result.sop_instance_uid == "1.2.3.4.5.1.1"

    def test_store_batch(self, sync_client, tmp_path: Path):
        files = []
        for i in range(3):
            f = tmp_path / f"test_{i}.dcm"
            f.write_bytes(b"\x00" * 128)
            files.append(str(f))

        mock_resp = make_mock_response(200, {"ID": f"1.2.3.4.{i}", "ParentStudy": "study"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            results = sync_client.store_batch(files)
            assert len(results) == 3
            assert all(r.success for r in results)

    def test_store_file_not_found(self, sync_client):
        with pytest.raises(DicomValidationError, match="not found"):
            sync_client.store("/nonexistent/file.dcm")


# =============================================================================
# Query Tests
# =============================================================================

class TestQueryOperations:
    def test_query_patients(self, sync_client, mock_orthanc_patient):
        mock_resp = make_mock_response(200, [mock_orthanc_patient])
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            patients = sync_client.list_patients()
            assert len(patients) == 1
            assert patients[0].patient_id == "P001"

    def test_query_patient(self, sync_client, mock_orthanc_patient):
        mock_resp = make_mock_response(200, mock_orthanc_patient)
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            patient = sync_client.get_patient("P001")
            assert patient.patient_id == "P001"
            assert patient.patient_name == "Test^Patient"

    def test_query_studies(self, sync_client, mock_orthanc_study):
        mock_resp = make_mock_response(200, [mock_orthanc_study])
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            studies = sync_client.query(patient_id="P001", modality="CT")
            assert len(studies) == 1
            assert studies[0].study_instance_uid == "1.2.3.4.5"

    def test_query_series(self, sync_client, mock_orthanc_series):
        mock_resp = make_mock_response(200, [mock_orthanc_series])
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            series = sync_client.query_series(study_uid="1.2.3.4.5", modality="CT")
            assert len(series) == 1
            assert series[0].series_instance_uid == "1.2.3.4.5.1"
            assert series[0].modality == "CT"

    def test_query_instances(self, sync_client, mock_orthanc_instance):
        mock_resp = make_mock_response(200, [mock_orthanc_instance])
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            instances = sync_client.query_instances(series_uid="1.2.3.4.5.1")
            assert len(instances) == 1
            assert instances[0].sop_instance_uid == "1.2.3.4.5.1.1"


# =============================================================================
# Retrieve Tests
# =============================================================================

class TestRetrieveOperations:
    def test_get_study(self, sync_client, mock_orthanc_study):
        mock_resp = make_mock_response(200, mock_orthanc_study)
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            study = sync_client.get_study("1.2.3.4.5")
            assert study.study_instance_uid == "1.2.3.4.5"
            assert study.study_description == "CT Chest"

    def test_get_series(self, sync_client, mock_orthanc_series):
        mock_resp = make_mock_response(200, mock_orthanc_series)
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            series = sync_client.get_series("1.2.3.4.5", "1.2.3.4.5.1")
            assert series.series_instance_uid == "1.2.3.4.5.1"
            assert series.modality == "CT"

    def test_get_instance(self, sync_client, mock_orthanc_instance):
        mock_resp = make_mock_response(200, mock_orthanc_instance)
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            instance = sync_client.get_instance("1.2.3.4.5", "1.2.3.4.5.1", "1.2.3.4.5.1.1")
            assert instance.sop_instance_uid == "1.2.3.4.5.1.1"


# =============================================================================
# System / Stats Tests
# =============================================================================

class TestSystemOperations:
    def test_get_system(self, sync_client, mock_system_info):
        mock_resp = make_mock_response(200, mock_system_info)
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            info = sync_client.get_system()
            assert info["Version"] == "26.1.0"
            assert info["Database"] == "PostgreSQL"

    def test_get_statistics(self, sync_client, mock_statistics):
        mock_resp = make_mock_response(200, mock_statistics)
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            stats = sync_client.get_statistics()
            assert stats.count_studies == 42
            assert stats.count_instances == 3840

    def test_get_changes(self, sync_client, mock_changes):
        mock_resp = make_mock_response(200, mock_changes)
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            changes = sync_client.get_changes(limit=10, since=0)
            assert len(changes["content"]) == 2
            assert changes["last"] == 2


# =============================================================================
# Archive / Anonymize Tests
# =============================================================================

class TestArchiveOperations:
    def test_archive_study(self, sync_client, tmp_path: Path):
        mock_resp = make_mock_response(200, content=b"PK\x03\x04", headers={"content-type": "application/zip"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            zip_data = sync_client.archive_study("1.2.3.4.5")
            assert zip_data == b"PK\x03\x04"

    def test_archive_series(self, sync_client, tmp_path: Path):
        mock_resp = make_mock_response(200, content=b"PK\x03\x04", headers={"content-type": "application/zip"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            zip_data = sync_client.archive_series("1.2.3.4.5", "1.2.3.4.5.1")
            assert zip_data == b"PK\x03\x04"

    def test_anonymize(self, sync_client, mock_orthanc_study):
        mock_resp = make_mock_response(200, {**mock_orthanc_study, "PatientName": "ANONYMIZED"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.anonymize("1.2.3.4.5", patient_name="ANONYMIZED")
            assert result["PatientName"] == "ANONYMIZED"


# =============================================================================
# Peers / Modalities Tests
# =============================================================================

class TestPeersModalities:
    def test_list_modalities(self, sync_client):
        mock_resp = make_mock_response(200, {
            "Modalities": [
                {"Name": "CT1", "AET": "CT_SCANNER", "Port": 2104, "Host": "192.168.1.10"},
            ]
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            modalities = sync_client.list_modalities()
            assert len(modalities) == 1
            assert modalities[0].name == "CT1"

    def test_list_peers(self, sync_client):
        mock_resp = make_mock_response(200, {
            "Peers": ["peer1", "peer2"],
            "Urls": ["http://peer1:8042", "http://peer2:8042"],
        })
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            peers = sync_client.list_peers()
            assert len(peers) == 2

    def test_ping_peer_success(self, sync_client):
        mock_resp = make_mock_response(200, {"Status": "OK"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            result = sync_client.ping_peer("peer1")
            assert result["Status"] == "OK"


# =============================================================================
# Exception Tests
# =============================================================================

class TestExceptions:
    def test_connection_error(self, sync_client):
        with patch.object(sync_client._client, "request", side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(DicomConnectionError):
                sync_client.list_patients()

    def test_not_found_error(self, sync_client):
        mock_resp = make_mock_response(404, {"ErrorMessage": "Not found"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            with pytest.raises(DicomNotFoundError):
                sync_client.get_patient("NONEXISTENT")

    def test_auth_error(self, sync_client):
        mock_resp = make_mock_response(401, {"ErrorMessage": "Unauthorized"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            with pytest.raises(DicomAuthenticationError):
                sync_client.list_patients()

    def test_server_error(self, sync_client):
        mock_resp = make_mock_response(500, {"ErrorMessage": "Internal error"})
        with patch.object(sync_client._client, "request", return_value=mock_resp):
            with pytest.raises(DicomServerError):
                sync_client.list_patients()
