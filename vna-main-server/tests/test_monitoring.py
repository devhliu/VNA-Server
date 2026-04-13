"""Tests for monitoring API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_monitoring_health(test_client: AsyncClient):
    """GET /v1/monitoring/health returns health checks."""
    resp = await test_client.get("/v1/monitoring/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "checks" in data
    assert isinstance(data["checks"], list)
    assert len(data["checks"]) >= 1
    # Each check should have component, status, message
    for check in data["checks"]:
        assert "component" in check
        assert "status" in check


@pytest.mark.asyncio
async def test_monitoring_metrics(test_client: AsyncClient):
    """GET /v1/monitoring/metrics returns metrics."""
    resp = await test_client.get("/v1/monitoring/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "database" in data
    db = data["database"]
    assert "resources_total" in db
    assert "patients_total" in db
    assert "labels_total" in db
    assert "webhooks_total" in db
    assert "sync_events_pending" in db


@pytest.mark.asyncio
async def test_monitoring_status(test_client: AsyncClient):
    """GET /v1/monitoring/status returns system status."""
    resp = await test_client.get("/v1/monitoring/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "health" in data
    assert "metrics" in data
    assert "alerts" in data
    assert "active" in data["alerts"]
    assert "firing" in data["alerts"]


@pytest.mark.asyncio
async def test_monitoring_component_health(test_client: AsyncClient):
    """GET /v1/monitoring/health/{component} returns specific component health."""
    resp = await test_client.get("/v1/monitoring/health/database")
    assert resp.status_code == 200
    data = resp.json()
    assert data["component"] == "database"
    assert "status" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_monitoring_unknown_component(test_client: AsyncClient):
    """GET /v1/monitoring/health/{component} returns error for unknown component."""
    resp = await test_client.get("/v1/monitoring/health/nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_monitoring_prometheus(test_client: AsyncClient):
    """GET /v1/monitoring/metrics/prometheus returns Prometheus format."""
    resp = await test_client.get("/v1/monitoring/metrics/prometheus")
    assert resp.status_code == 200
    # Should be plain text with Prometheus format
    assert "vna_resources_total" in resp.text
