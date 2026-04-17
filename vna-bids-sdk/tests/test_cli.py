"""Tests for the BIDS Server CLI."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bids_sdk.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nii.gz", delete=False) as f:
        f.write("fake data" * 100)
        f.flush()
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


class TestCLIBasics:
    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "BIDS Server CLI" in result.output

    def test_upload_help(self, runner):
        result = runner.invoke(cli, ["upload", "--help"])
        assert result.exit_code == 0
        assert "--subject" in result.output

    def test_download_help(self, runner):
        result = runner.invoke(cli, ["download", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output

    def test_query_help(self, runner):
        result = runner.invoke(cli, ["query", "--help"])
        assert result.exit_code == 0

    def test_label_help(self, runner):
        result = runner.invoke(cli, ["label", "--help"])
        assert result.exit_code == 0

    def test_subjects_help(self, runner):
        result = runner.invoke(cli, ["subjects", "--help"])
        assert result.exit_code == 0

    def test_sessions_help(self, runner):
        result = runner.invoke(cli, ["sessions", "--help"])
        assert result.exit_code == 0

    def test_tasks_help(self, runner):
        result = runner.invoke(cli, ["tasks", "--help"])
        assert result.exit_code == 0

    def test_verify_help(self, runner):
        result = runner.invoke(cli, ["verify", "--help"])
        assert result.exit_code == 0

    def test_rebuild_help(self, runner):
        result = runner.invoke(cli, ["rebuild", "--help"])
        assert result.exit_code == 0


class TestCLIUpload:
    @patch("bids_sdk.cli.BidsClient")
    def test_upload_basic(self, mock_client_cls, runner, tmp_file):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Resource
        mock_client.upload.return_value = Resource(resource_id="res-01", filename="test.nii.gz")

        result = runner.invoke(cli, [
            "upload", str(tmp_file),
            "--subject", "sub-01",
            "--session", "ses-01",
            "--modality", "anat",
            "--server", "http://localhost:8080",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["resource_id"] == "res-01"

    @patch("bids_sdk.cli.BidsClient")
    def test_upload_without_session(self, mock_client_cls, runner, tmp_file):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Resource
        mock_client.upload.return_value = Resource(resource_id="res-01")

        result = runner.invoke(cli, [
            "upload", str(tmp_file),
            "--subject", "sub-01",
            "--modality", "anat",
            "--server", "http://localhost:8080",
            "--json",
        ])
        assert result.exit_code == 0
        mock_client.upload.assert_called_once()
        assert mock_client.upload.call_args.args[2] is None

    @patch("bids_sdk.cli.BidsClient")
    def test_upload_with_labels(self, mock_client_cls, runner, tmp_file):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Resource
        mock_client.upload.return_value = Resource(resource_id="res-01")

        result = runner.invoke(cli, [
            "upload", str(tmp_file),
            "--subject", "sub-01",
            "--session", "ses-01",
            "--modality", "anat",
            "--server", "http://localhost:8080",
            "--labels", "tag1,tag2",
            "--json",
        ])
        assert result.exit_code == 0

    @patch("bids_sdk.cli.BidsClient")
    def test_upload_chunked(self, mock_client_cls, runner, tmp_file):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Resource
        mock_client.upload_chunked.return_value = Resource(resource_id="res-01")

        result = runner.invoke(cli, [
            "upload", str(tmp_file),
            "--subject", "sub-01",
            "--session", "ses-01",
            "--modality", "anat",
            "--server", "http://localhost:8080",
            "--chunked",
            "--json",
        ])
        assert result.exit_code == 0

    def test_upload_missing_file(self, runner):
        result = runner.invoke(cli, [
            "upload", "/nonexistent/file.nii.gz",
            "--subject", "sub-01",
            "--session", "ses-01",
            "--modality", "anat",
            "--server", "http://localhost:8080",
        ])
        assert result.exit_code != 0


class TestCLIDownload:
    @patch("bids_sdk.cli.BidsClient")
    def test_download_basic(self, mock_client_cls, runner, tmp_file):
        output = tmp_file.parent / "cli_dl.nii.gz"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        mock_client.download.return_value = output

        result = runner.invoke(cli, [
            "download", "res-01",
            "--output", str(output),
            "--server", "http://localhost:8080",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "path" in data

    @patch("bids_sdk.cli.BidsClient")
    def test_download_with_range(self, mock_client_cls, runner, tmp_file):
        output = tmp_file.parent / "cli_range_dl.nii.gz"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        mock_client.download_stream.return_value = output

        result = runner.invoke(cli, [
            "download", "res-01",
            "--output", str(output),
            "--server", "http://localhost:8080",
            "--range-start", "0",
            "--range-end", "100",
        ])
        assert result.exit_code == 0


class TestCLIQuery:
    @patch("bids_sdk.cli.BidsClient")
    def test_query_basic(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import QueryResult, Resource
        mock_client.query.return_value = QueryResult(
            resources=[Resource(resource_id="res-01", filename="T1w.nii.gz")],
            total=1,
        )

        result = runner.invoke(cli, [
            "query",
            "--server", "http://localhost:8080",
            "--subject", "sub-01",
            "--modality", "anat",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    @patch("bids_sdk.cli.BidsClient")
    def test_query_verbose(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import QueryResult
        mock_client.query.return_value = QueryResult(resources=[], total=0)

        result = runner.invoke(cli, [
            "query",
            "--server", "http://localhost:8080",
            "--verbose",
        ])
        assert result.exit_code == 0
        assert "Found 0 results" in result.output


class TestCLILabel:
    @patch("bids_sdk.cli.BidsClient")
    def test_label_get(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        mock_client.get_labels.return_value = [{"key": "quality", "value": "good"}]

        result = runner.invoke(cli, [
            "label", "res-01",
            "--server", "http://localhost:8080",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["key"] == "quality"

    @patch("bids_sdk.cli.BidsClient")
    def test_label_set(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        mock_client.set_labels.return_value = [{"key": "new-tag"}]

        result = runner.invoke(cli, [
            "label", "res-01",
            "--server", "http://localhost:8080",
            "--set", '["new-tag"]',
            "--json",
        ])
        assert result.exit_code == 0

    @patch("bids_sdk.cli.BidsClient")
    def test_label_patch(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        mock_client.patch_labels.return_value = [{"key": "added"}]

        result = runner.invoke(cli, [
            "label", "res-01",
            "--server", "http://localhost:8080",
            "--add", '["added"]',
            "--remove", "old-tag",
            "--json",
        ])
        assert result.exit_code == 0


class TestCLISubjects:
    @patch("bids_sdk.cli.BidsClient")
    def test_list_subjects(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Subject
        mock_client.list_subjects.return_value = [
            Subject(subject_id="sub-01"),
            Subject(subject_id="sub-02"),
        ]

        result = runner.invoke(cli, [
            "subjects",
            "--server", "http://localhost:8080",
            "--list",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2

    @patch("bids_sdk.cli.BidsClient")
    def test_create_subject(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Subject
        mock_client.create_subject.return_value = Subject(subject_id="sub-03")

        result = runner.invoke(cli, [
            "subjects",
            "--server", "http://localhost:8080",
            "--create", "sub-03",
            "--json",
        ])
        assert result.exit_code == 0

    @patch("bids_sdk.cli.BidsClient")
    def test_get_subject(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Subject
        mock_client.get_subject.return_value = Subject(subject_id="sub-01")

        result = runner.invoke(cli, [
            "subjects",
            "--server", "http://localhost:8080",
            "--get", "sub-01",
            "--json",
        ])
        assert result.exit_code == 0


class TestCLISessions:
    @patch("bids_sdk.cli.BidsClient")
    def test_list_sessions(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Session
        mock_client.list_sessions.return_value = [
            Session(session_id="ses-01", subject_id="sub-01"),
        ]

        result = runner.invoke(cli, [
            "sessions",
            "--server", "http://localhost:8080",
            "--subject", "sub-01",
            "--list",
            "--json",
        ])
        assert result.exit_code == 0

    @patch("bids_sdk.cli.BidsClient")
    def test_create_session(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Session
        mock_client.create_session.return_value = Session(
            session_id="ses-02", subject_id="sub-01"
        )

        result = runner.invoke(cli, [
            "sessions",
            "--server", "http://localhost:8080",
            "--subject", "sub-01",
            "--create", "ses-02",
            "--json",
        ])
        assert result.exit_code == 0


class TestCLITasks:
    @patch("bids_sdk.cli.BidsClient")
    def test_submit_task(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Task
        mock_client.submit_task.return_value = Task(
            task_id="t1", action="convert", status="pending", resource_ids=["r1"]
        )

        result = runner.invoke(cli, [
            "tasks",
            "--server", "http://localhost:8080",
            "--submit", "convert",
            "--resource-ids", "r1",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["task_id"] == "t1"

    @patch("bids_sdk.cli.BidsClient")
    def test_task_status(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Task
        mock_client.get_task.return_value = Task(
            task_id="t1", action="convert", status="completed"
        )

        result = runner.invoke(cli, [
            "tasks",
            "--server", "http://localhost:8080",
            "--status", "t1",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "completed"

    @patch("bids_sdk.cli.BidsClient")
    def test_cancel_task(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Task
        mock_client.cancel_task.return_value = Task(
            task_id="t1", action="convert", status="cancelled"
        )

        result = runner.invoke(cli, [
            "tasks",
            "--server", "http://localhost:8080",
            "--cancel", "t1",
            "--json",
        ])
        assert result.exit_code == 0

    def test_tasks_no_action(self, runner):
        result = runner.invoke(cli, [
            "tasks",
            "--server", "http://localhost:8080",
        ])
        assert result.exit_code != 0


class TestCLIVerify:
    @patch("bids_sdk.cli.BidsClient")
    def test_verify(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        mock_client.verify.return_value = {"status": "ok", "checked": 100}

        result = runner.invoke(cli, [
            "verify",
            "--server", "http://localhost:8080",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"


class TestCLIRebuild:
    @patch("bids_sdk.cli.BidsClient")
    def test_rebuild(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        mock_client.rebuild.return_value = {"status": "started"}

        result = runner.invoke(cli, [
            "rebuild",
            "--server", "http://localhost:8080",
            "--json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "started"

    @patch("bids_sdk.cli.BidsClient")
    def test_rebuild_clear(self, mock_client_cls, runner):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        mock_client.rebuild.return_value = {"status": "started"}

        result = runner.invoke(cli, [
            "rebuild",
            "--server", "http://localhost:8080",
            "--clear-existing",
            "--json",
        ])
        assert result.exit_code == 0
        mock_client.rebuild.assert_called_once_with(target=None, clear_existing=True)


class TestCLIVerbose:
    @patch("bids_sdk.cli.BidsClient")
    def test_upload_verbose(self, mock_client_cls, runner, tmp_file):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        from bids_sdk.models import Resource
        mock_client.upload.return_value = Resource(resource_id="res-01")

        result = runner.invoke(cli, [
            "upload", str(tmp_file),
            "--subject", "sub-01",
            "--session", "ses-01",
            "--modality", "anat",
            "--server", "http://localhost:8080",
            "--verbose",
        ])
        assert result.exit_code == 0
        assert "Upload successful!" in result.output
