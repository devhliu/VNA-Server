"""Pytest configuration and fixtures for VNA integration tests."""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: integration test requiring real services")
    config.addinivalue_line("markers", "slow: slow running test")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def docker_services():
    import subprocess
    compose_file = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d", "--quiet-pull"],
        check=False,
        capture_output=True,
    )
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "wait", "postgres", "-t", "30"],
        check=False,
    )
    yield
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "down", "-v", "--remove-orphans"],
        check=False,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def orthanc_url() -> str:
    return os.environ.get("ORTHANC_URL", "http://localhost:8042")


@pytest.fixture(scope="session")
def main_server_url() -> str:
    return os.environ.get("MAIN_SERVER_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def bids_server_url() -> str:
    return os.environ.get("BIDS_SERVER_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def postgres_url() -> str:
    return os.environ.get(
        "POSTGRES_URL",
        "postgresql+asyncpg://orthanc:orthanc@localhost:5432/vna_test",
    )


@pytest.fixture
def wait_for_service():
    import asyncio
    import httpx

    async def _wait(url: str, path: str = "/", timeout: float = 60.0, interval: float = 1.0):
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{url}{path}")
                    if resp.is_success or resp.status_code == 401:
                        return True
            except Exception:
                pass
            await asyncio.sleep(interval)
        return False

    return _wait
