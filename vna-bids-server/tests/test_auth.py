"""Tests for API key protection on public BIDS routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from bids_server.config import settings
from bids_server.main import app


@pytest.mark.asyncio
async def test_public_routes_require_token_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "bids_api_key", "bids-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/bidsweb/v1/subjects")

    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_public_routes_accept_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "bids_api_key", "bids-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer bids-secret"},
    ) as client:
        resp = await client.get("/bidsweb/v1/subjects")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_and_internal_routes_stay_open(monkeypatch):
    monkeypatch.setattr(settings, "bids_api_key", "bids-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        internal = await client.post("/v1/internal/status")

    assert health.status_code == 200
    assert internal.status_code == 200

