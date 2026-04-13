"""Tests for health and internal status endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from vna_main.main import app
from vna_main.models.database import get_session


@pytest.fixture
async def client(db_session):
    """Client without DB dependency (health/internal don't need it)."""
    async def override():
        yield db_session
    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "vna-main-server"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """GET /v1/health returns expected keys."""
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "live" in data
    assert "ready" in data
    assert "status" in data
    assert "components" in data
    assert data["live"] is True
    assert data["service"] == "vna-main-server"


@pytest.mark.asyncio
async def test_internal_status(client: AsyncClient):
    """GET /v1/internal/status returns service info."""
    resp = await client.get("/v1/internal/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "vna-main-server"
    assert data["live"] is True
    assert "version" in data
    assert "timestamp" in data
