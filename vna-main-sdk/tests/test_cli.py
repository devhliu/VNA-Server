"""CLI tests with CliRunner."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vna_main_sdk.cli import cli
from vna_main_sdk.models import (
    DataType,
    HealthStatus,
    Label,
    Patient,
    QueryResult,
    Resource,
    ServerRegistration,
    SourceType,
    SyncStatus,
    TagInfo,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _make_resource(resource_id: str = "res-1", patient_ref: str = "p1", source_type: str = "dicom") -> Resource:
    return Resource(
        resource_id=resource_id,
        patient_ref=patient_ref,
        source_type=SourceType(source_type),
        data_type=DataType.IMAGING,
        labels=[],
        metadata={},
    )


def _make_patient(patient_ref: str = "p1") -> Patient:
    return Patient(
        patient_ref=patient_ref,
        hospital_id="H123",
        source="hospital_a",
        resource_count=5,
        resources=[],
    )


def _make_health() -> HealthStatus:
    return HealthStatus(status="ok", version="1.0.0", database="ok", uptime_seconds=100.0)


def _make_sync_status() -> SyncStatus:
    return SyncStatus(dicom={"status": "idle"}, bids={"status": "idle"}, last_sync=None, events=[])


# ─── Resources CLI ──────────────────────────────────────────────────────────────

@patch("vna_main_sdk.cli.VnaClient")
def test_resources_list(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.list_resources.return_value = QueryResult(total=2, limit=50, offset=0, resources=[_make_resource("r1"), _make_resource("r2")])
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["resources", "list"])
    assert result.exit_code == 0
    assert "Total: 2" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_resources_list_json(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.list_resources.return_value = QueryResult(total=1, resources=[_make_resource()])
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["--json", "resources", "list"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total"] == 1


@patch("vna_main_sdk.cli.VnaClient")
def test_resources_list_with_filters(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.list_resources.return_value = QueryResult(total=0, resources=[])
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["resources", "list", "--patient", "p1", "--type", "imaging", "--source", "dicom"])
    assert result.exit_code == 0
    mock_client.list_resources.assert_called_once()


@patch("vna_main_sdk.cli.VnaClient")
def test_resources_get(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.get_resource.return_value = _make_resource("res-123")
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["resources", "get", "res-123"])
    assert result.exit_code == 0
    assert "res-123" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_resources_get_json(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.get_resource.return_value = _make_resource("r42")
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["--json", "resources", "get", "r42"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["resource_id"] == "r42"


@patch("vna_main_sdk.cli.VnaClient")
def test_resources_register(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.register_resource.return_value = _make_resource("new-1")
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["resources", "register", "--patient", "p1", "--source", "dicom", "--dicom-study-uid", "1.2.3.4"])
    assert result.exit_code == 0
    assert "new-1" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_resources_register_bids(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.register_resource.return_value = _make_resource("bids-1", source_type="bids")
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["resources", "register", "--patient", "p2", "--source", "bids", "--bids-path", "/data/sub-01"])
    assert result.exit_code == 0
    assert "bids-1" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_resources_delete(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.delete_resource.return_value = {"deleted": True}
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["resources", "delete", "res-1"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_resources_delete_json(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.delete_resource.return_value = {"deleted": True}
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["--json", "resources", "delete", "res-1"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["deleted"] is True


# ─── Patients CLI ───────────────────────────────────────────────────────────────

@patch("vna_main_sdk.cli.VnaClient")
def test_patients_list(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.list_patients.return_value = {"total": 3, "patients": [{"patient_ref": "p1"}, {"patient_ref": "p2"}]}
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["patients", "list"])
    assert result.exit_code == 0
    assert "Total: 3" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_patients_get(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.get_patient.return_value = _make_patient("p1")
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["patients", "get", "p1"])
    assert result.exit_code == 0
    assert "p1" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_patients_create(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.create_patient.return_value = _make_patient("p-new")
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["patients", "create", "p-new", "--hospital-id", "H456", "--source", "hospital_b"])
    assert result.exit_code == 0
    assert "Created" in result.output


# ─── Labels CLI ─────────────────────────────────────────────────────────────────

@patch("vna_main_sdk.cli.VnaClient")
def test_labels_get(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.get_labels.return_value = [Label(key="modality", value="MRI"), Label(key="site", value=None)]
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["labels", "get", "r1"])
    assert result.exit_code == 0
    assert "modality=MRI" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_labels_get_empty(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.get_labels.return_value = []
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["labels", "get", "r1"])
    assert result.exit_code == 0
    assert "No labels" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_labels_set(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.set_labels.return_value = [Label(key="modality", value="CT")]
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["labels", "set", "r1", "--labels", '{"modality": "CT"}'])
    assert result.exit_code == 0
    assert "Set 1 labels" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_labels_patch(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.patch_labels.return_value = [Label(key="k1", value="v1"), Label(key="k2", value="v2")]
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["labels", "patch", "r1", "--add", '{"k1": "v1"}', "--remove", "old_key"])
    assert result.exit_code == 0
    assert "Patched" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_labels_tags(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.list_all_tags.return_value = [TagInfo(key="modality", count=10), TagInfo(key="site", count=5)]
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["labels", "tags"])
    assert result.exit_code == 0
    assert "modality: 10" in result.output


# ─── Query CLI ──────────────────────────────────────────────────────────────────

@patch("vna_main_sdk.cli.VnaClient")
def test_query(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.query.return_value = QueryResult(total=5, resources=[_make_resource(f"r{i}") for i in range(5)])
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["query", "--patient", "p1"])
    assert result.exit_code == 0
    assert "Total: 5" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_query_json(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.query.return_value = QueryResult(total=0, resources=[])
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["--json", "query", "--search", "brain"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total"] == 0


# ─── Sync CLI ───────────────────────────────────────────────────────────────────

@patch("vna_main_sdk.cli.VnaClient")
def test_sync_status(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.sync_status.return_value = _make_sync_status()
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["sync", "status"])
    assert result.exit_code == 0
    assert "Sync Status" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_sync_trigger(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.trigger_sync.return_value = _make_sync_status()
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["sync", "trigger", "--source", "dicom"])
    assert result.exit_code == 0
    assert "Sync triggered" in result.output


# ─── Health CLI ─────────────────────────────────────────────────────────────────

@patch("vna_main_sdk.cli.VnaClient")
def test_health(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.health.return_value = _make_health()
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["health"])
    assert result.exit_code == 0
    assert "Status: ok" in result.output


@patch("vna_main_sdk.cli.VnaClient")
def test_health_json(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.health.return_value = _make_health()
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["--json", "health"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"


# ─── Error Handling CLI ─────────────────────────────────────────────────────────

@patch("vna_main_sdk.cli.VnaClient")
def test_error_handling(mock_cls, runner: CliRunner) -> None:
    from vna_main_sdk.client import VnaClientError
    mock_client = MagicMock()
    mock_client.health.side_effect = VnaClientError("Connection refused")
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["health"])
    assert result.exit_code != 0
    assert "Error" in result.output


# ─── Base URL Option ────────────────────────────────────────────────────────────

@patch("vna_main_sdk.cli.VnaClient")
def test_custom_base_url(mock_cls, runner: CliRunner) -> None:
    mock_client = MagicMock()
    mock_client.health.return_value = _make_health()
    mock_cls.return_value = mock_client
    result = runner.invoke(cli, ["--base-url", "http://custom:9000", "health"])
    assert result.exit_code == 0
    mock_cls.assert_called_with(base_url="http://custom:9000", api_key=None)
