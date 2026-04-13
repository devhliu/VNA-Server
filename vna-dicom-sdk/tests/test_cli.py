"""Integration tests for the DICOM CLI."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from dicom_sdk.cli import cli
from dicom_sdk.models import (
    StudyMetadata,
    ServerStatistics,
    ModalityInfo,
    StoreResult,
    QueryResult,
)


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_client():
    """Create a mock DicomClient."""
    with patch("dicom_sdk.cli.DicomClient") as MockClient:
        instance = MagicMock()
        MockClient.return_value.__enter__.return_value = instance
        yield instance


class TestCLIStore:
    def test_store_success(self, runner, mock_client, tmp_path):
        test_file = tmp_path / "test.dcm"
        test_file.write_bytes(b"\x00" * 132)

        mock_client.store.return_value = StoreResult(
            success=True,
            sop_instance_uid="inst-123",
            status_code=200,
        )

        result = runner.invoke(cli, [
            "store", str(test_file),
            "--server", "http://localhost:8042",
        ])
        assert result.exit_code == 0

    def test_store_json_output(self, runner, mock_client, tmp_path):
        test_file = tmp_path / "test.dcm"
        test_file.write_bytes(b"\x00" * 132)

        mock_client.store.return_value = StoreResult(
            success=True,
            sop_instance_uid="inst-123",
            status_code=200,
        )

        result = runner.invoke(cli, [
            "store", str(test_file),
            "--server", "http://localhost:8042",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["success"] is True

    def test_store_file_not_found(self, runner):
        result = runner.invoke(cli, [
            "store", "/nonexistent/file.dcm",
            "--server", "http://localhost:8042",
        ])
        assert result.exit_code != 0


class TestCLIQuery:
    def test_query_studies(self, runner, mock_client):
        mock_client.query.return_value = [
            QueryResult(
                study_instance_uid="1.2.3.4",
                patient_id="P001",
                patient_name="DOE^JOHN",
                study_date="20240101",
            ),
        ]

        result = runner.invoke(cli, [
            "query",
            "--server", "http://localhost:8042",
            "--patient-id", "P001",
        ])
        assert result.exit_code == 0

    def test_query_json_output(self, runner, mock_client):
        mock_client.query.return_value = [
            QueryResult(study_instance_uid="1.2.3.4", patient_id="P001"),
        ]

        result = runner.invoke(cli, [
            "query",
            "--server", "http://localhost:8042",
            "--patient-id", "P001",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["patient_id"] == "P001"

    def test_query_empty(self, runner, mock_client):
        mock_client.query.return_value = []

        result = runner.invoke(cli, [
            "query",
            "--server", "http://localhost:8042",
            "--patient-id", "NONEXISTENT",
        ])
        assert result.exit_code == 0


class TestCLIRetrieve:
    def test_retrieve_success(self, runner, mock_client):
        mock_client.retrieve.return_value = [b"\x00" * 132]

        result = runner.invoke(cli, [
            "retrieve", "study-uid-123",
            "--server", "http://localhost:8042",
            "--output", "/tmp/test_output",
        ])
        assert result.exit_code == 0
        assert "1 file(s)" in result.output


class TestCLIDelete:
    def test_delete_with_confirmation(self, runner, mock_client):
        mock_client.delete.return_value = True

        result = runner.invoke(cli, [
            "delete", "study-uid-123",
            "--server", "http://localhost:8042",
            "--yes",
        ])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    def test_delete_aborted(self, runner, mock_client):
        result = runner.invoke(cli, [
            "delete", "study-uid-123",
            "--server", "http://localhost:8042",
        ], input="n\n")
        assert result.exit_code != 0  # Aborted


class TestCLIInfo:
    def test_info_success(self, runner, mock_client):
        mock_client.get_study.return_value = StudyMetadata(
            study_instance_uid="1.2.3.4",
            patient_id="P001",
            patient_name="DOE^JOHN",
            study_date="20240101",
            study_description="Chest CT",
            number_of_series=2,
        )

        result = runner.invoke(cli, [
            "info", "1.2.3.4",
            "--server", "http://localhost:8042",
        ])
        assert result.exit_code == 0
        assert "1.2.3.4" in result.output

    def test_info_json(self, runner, mock_client):
        mock_client.get_study.return_value = StudyMetadata(
            study_instance_uid="1.2.3.4",
            patient_id="P001",
        )

        result = runner.invoke(cli, [
            "info", "1.2.3.4",
            "--server", "http://localhost:8042",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["study_instance_uid"] == "1.2.3.4"


class TestCLIStats:
    def test_stats_success(self, runner, mock_client):
        mock_client.get_statistics.return_value = ServerStatistics(
            count_studies=42,
            count_series=150,
            count_instances=3000,
        )

        result = runner.invoke(cli, [
            "stats",
            "--server", "http://localhost:8042",
        ])
        assert result.exit_code == 0
        assert "42" in result.output

    def test_stats_json(self, runner, mock_client):
        mock_client.get_statistics.return_value = ServerStatistics(
            count_studies=42,
            count_series=150,
            count_instances=3000,
        )

        result = runner.invoke(cli, [
            "stats",
            "--server", "http://localhost:8042",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count_studies"] == 42


class TestCLIRender:
    def test_render_success(self, runner, mock_client):
        mock_client.render.return_value = b"\x89PNG"

        result = runner.invoke(cli, [
            "render", "study-uid", "series-uid", "sop-uid",
            "--server", "http://localhost:8042",
            "--output", "/tmp/test.png",
        ])
        assert result.exit_code == 0
        assert "Rendered" in result.output


class TestCLIModalities:
    def test_modalities_list(self, runner, mock_client):
        mock_client.list_modalities.return_value = [
            ModalityInfo(name="ORTHANC", aet="ORTHANC", host="127.0.0.1", port=4242),
        ]

        result = runner.invoke(cli, [
            "modalities",
            "--server", "http://localhost:8042",
        ])
        assert result.exit_code == 0


class TestCLIVersion:
    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCLIVerbose:
    def test_verbose_retrieve(self, runner, mock_client):
        mock_client.retrieve.return_value = [b"\x00" * 100]

        result = runner.invoke(cli, [
            "retrieve", "study-uid",
            "--server", "http://localhost:8042",
            "--output", "/tmp/test_output",
            "--verbose",
        ])
        assert result.exit_code == 0
        assert "100 bytes" in result.output
