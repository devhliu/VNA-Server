"""Tests for DICOM change watchers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from dicom_sdk.sync_watcher import ChangeWatcher, SyncWatcher


@pytest.mark.asyncio
async def test_change_watcher_posts_to_main_sync_endpoint():
    dicom_client = MagicMock()
    watcher = ChangeWatcher(
        dicom_client=dicom_client,
        vna_server_url="http://localhost:8000",
        api_key="secret",
    )

    response = MagicMock(spec=httpx.Response)
    response.is_success = True

    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    async_client = MagicMock()
    async_client.__aenter__ = AsyncMock(return_value=client)
    async_client.__aexit__ = AsyncMock(return_value=False)

    with patch("dicom_sdk.sync_watcher.httpx.AsyncClient", return_value=async_client):
        await watcher._send_event("created", "orthanc-study-1", "Study")

    client.post.assert_called_once()
    _, kwargs = client.post.call_args
    assert client.post.call_args.args[0] == "http://localhost:8000/api/v1/sync/event"
    assert kwargs["headers"] == {"Authorization": "Bearer secret"}
    assert kwargs["json"] == {
        "source_db": "dicom",
        "event_type": "resource.created",
        "resource_id": "orthanc-study-1",
        "payload": {
            "resource_type": "Study",
            "source_type": "dicom_only",
            "data_type": "dicom",
        },
    }


@pytest.mark.asyncio
async def test_change_watcher_handles_http_errors_from_change_poll():
    dicom_client = MagicMock()
    dicom_client.get_changes = MagicMock(side_effect=httpx.TimeoutException("timeout"))
    watcher = ChangeWatcher(dicom_client=dicom_client, vna_server_url="http://localhost:8000")

    await watcher._process_changes()


def test_sync_watcher_posts_to_main_sync_endpoint():
    dicom_client = MagicMock()
    watcher = SyncWatcher(
        dicom_client=dicom_client,
        vna_server_url="http://localhost:8000",
        api_key="secret",
    )

    response = MagicMock(spec=httpx.Response)
    response.is_success = True

    client = MagicMock()
    client.post = MagicMock(return_value=response)

    sync_client = MagicMock()
    sync_client.__enter__ = MagicMock(return_value=client)
    sync_client.__exit__ = MagicMock(return_value=False)

    with patch("dicom_sdk.sync_watcher.httpx.Client", return_value=sync_client):
        watcher._send_event("deleted", "orthanc-study-1", "Study")

    client.post.assert_called_once()
    _, kwargs = client.post.call_args
    assert client.post.call_args.args[0] == "http://localhost:8000/api/v1/sync/event"
    assert kwargs["headers"] == {"Authorization": "Bearer secret"}
    assert kwargs["json"]["event_type"] == "resource.deleted"


def test_sync_watcher_handles_http_errors_from_change_poll():
    dicom_client = MagicMock()
    dicom_client.get_changes = MagicMock(side_effect=httpx.TimeoutException("timeout"))
    watcher = SyncWatcher(dicom_client=dicom_client, vna_server_url="http://localhost:8000")

    watcher._process_changes()
