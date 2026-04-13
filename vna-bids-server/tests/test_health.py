"""Health contract tests and basic endpoint availability."""
from __future__ import annotations

import pytest

import bids_server.main as main_module


@pytest.mark.asyncio
class TestHealthContract:
    async def test_health_payload_shape(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert {"live", "ready", "degraded", "checks", "stats"} <= set(body)

    async def test_health_not_ready_on_storage_failure(self, client, monkeypatch):
        monkeypatch.setattr(main_module, "check_storage", lambda: False)
        resp = await client.get("/health")
        assert resp.json()["ready"] is False

    async def test_health_not_ready_on_database_failure(self, client, monkeypatch):
        async def fake_db_check():
            return False

        monkeypatch.setattr(main_module, "check_database", fake_db_check)
        resp = await client.get("/health")
        assert resp.json()["ready"] is False

    async def test_health_degraded_on_failed_webhook(self, client, seeded_failed_delivery):
        resp = await client.get("/health")
        body = resp.json()
        assert body["degraded"] is True
        assert body["stats"]["failed_webhooks"] == 1

    async def test_health_threshold_boundaries(self, client, seeded_boundary_retry_state):
        resp = await client.get("/health")
        body = resp.json()
        assert body["stats"]["retrying_webhooks"] == 10
        assert body["stats"]["retrying_tasks"] == 5
        assert body["degraded"] is False

    async def test_health_degraded_above_thresholds(self, client, seeded_retry_backlog):
        resp = await client.get("/health")
        body = resp.json()
        assert body["stats"]["retrying_webhooks"] > 10
        assert body["stats"]["retrying_tasks"] > 5
        assert body["degraded"] is True


# --- Basic endpoint availability smoke tests ---

@pytest.mark.asyncio
async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "BIDS Server"


@pytest.mark.asyncio
async def test_internal_status(client):
    resp = await client.post("/api/v1/internal/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "bids-server"
    assert body["live"] is True
