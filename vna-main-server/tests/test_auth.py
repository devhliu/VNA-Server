"""Tests for API key protection on public main-server routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from vna_main.config import settings
from vna_main.main import app


@pytest.mark.asyncio
async def test_public_routes_require_token_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "VNA_API_KEY", "main-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/resources")

    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_public_routes_accept_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "VNA_API_KEY", "main-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer main-secret"},
    ) as client:
        resp = await client.get("/api/v1/resources")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_and_internal_routes_stay_open(monkeypatch):
    monkeypatch.setattr(settings, "VNA_API_KEY", "main-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/v1/health")
        internal = await client.get("/api/v1/internal/status")

    assert health.status_code == 200
    assert internal.status_code == 200

