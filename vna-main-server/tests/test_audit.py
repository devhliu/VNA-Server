"""Tests for audit log API."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_audit_logs(test_client: AsyncClient):
    resp = await test_client.get("/v1/audit/logs")
    assert resp.status_code == 200
    assert "items" in resp.json()
    assert "total" in resp.json()


@pytest.mark.asyncio
async def test_audit_logs_filtered(test_client: AsyncClient):
    resp = await test_client.get("/v1/audit/logs", params={"action": "create"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(e["action"] == "create" for e in data["items"])
