"""Shared HTTP client pool for outgoing requests to sub-servers.

Every service (routing, webhook delivery, patient sync, sync) should use
``get_http_client()`` instead of creating per-request ``httpx.AsyncClient``
instances.  The client is created lazily on first use and closed during
application shutdown via ``close_http_client()``.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return the shared async HTTP client, creating it on first call."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
            ),
            follow_redirects=True,
        )
    return _http_client


async def close_http_client() -> None:
    """Close the shared HTTP client.  Safe to call multiple times."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
        logger.info("Shared HTTP client closed")
