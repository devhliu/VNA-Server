"""Routing service - route requests to appropriate sub-servers."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import httpx

from vna_main.config import settings
from vna_main.services.http_client import get_http_client

logger = logging.getLogger(__name__)


def _sanitize_path(path: str) -> str:
    """Sanitize a proxy path to prevent path traversal attacks."""
    # Remove any path traversal components
    cleaned = path.replace("../", "").replace("..\\", "")
    # Ensure no double slashes
    while "//" in cleaned:
        cleaned = cleaned.replace("//", "/")
    return cleaned


class RoutingService:
    """Routes requests to DICOM (Orthanc) or BIDS servers."""

    def __init__(
        self,
        dicom_url: str | None = None,
        bids_url: str | None = None,
    ):
        self.dicom_url = dicom_url or settings.DICOM_SERVER_URL
        self.bids_url = bids_url or settings.BIDS_SERVER_URL

    def dicom_auth(self) -> tuple[str, str] | None:
        """Return DICOM server authentication credentials."""
        if settings.DICOM_SERVER_USER and settings.DICOM_SERVER_PASSWORD:
            return (settings.DICOM_SERVER_USER, settings.DICOM_SERVER_PASSWORD)
        return None

    def bids_auth_headers(self) -> dict[str, str]:
        if not settings.BIDS_SERVER_API_KEY:
            return {}
        return {"Authorization": f"Bearer {settings.BIDS_SERVER_API_KEY}"}

    async def health_check_dicom(self) -> dict[str, Any]:
        try:
            client = get_http_client()
            resp = await client.get(f"{self.dicom_url}/system", auth=self.dicom_auth())
            resp.raise_for_status()
            return {"status": "healthy", "url": self.dicom_url, "info": resp.json()}
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as e:
            logger.error("DICOM health check failed for %s: %s", self.dicom_url, e, exc_info=True)
            return {"status": "unhealthy", "url": self.dicom_url, "error": str(e)}

    async def health_check_bids(self) -> dict[str, Any]:
        try:
            client = get_http_client()
            resp = await client.get(f"{self.bids_url}/health")
            resp.raise_for_status()
            return {"status": "healthy", "url": self.bids_url, "info": resp.json()}
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as e:
            logger.error("BIDS health check failed for %s: %s", self.bids_url, e, exc_info=True)
            return {"status": "unhealthy", "url": self.bids_url, "error": str(e)}

    async def proxy_to_dicom(self, path: str, method: str = "GET", **kwargs) -> dict[str, Any]:
        safe_path = _sanitize_path(path)
        url = f"{self.dicom_url}/{safe_path.lstrip('/')}"
        client = get_http_client()
        resp = await client.request(method, url, auth=self.dicom_auth(), **kwargs)
        resp.raise_for_status()
        return {"status_code": resp.status_code, "data": resp.json() if resp.content else None}

    async def proxy_to_bids(self, path: str, method: str = "GET", **kwargs) -> dict[str, Any]:
        safe_path = _sanitize_path(path)
        url = f"{self.bids_url}/{safe_path.lstrip('/')}"
        headers = dict(kwargs.pop("headers", {}))
        headers.update(self.bids_auth_headers())
        client = get_http_client()
        resp = await client.request(method, url, headers=headers or None, **kwargs)
        resp.raise_for_status()
        return {"status_code": resp.status_code, "data": resp.json() if resp.content else None}

    async def unified_health(self) -> dict[str, Any]:
        """Check health of all sub-servers."""
        dicom_health = await self.health_check_dicom()
        bids_health = await self.health_check_bids()
        overall = "healthy" if (
            dicom_health["status"] == "healthy" and bids_health["status"] == "healthy"
        ) else "degraded"
        return {
            "overall": overall,
            "dicom": dicom_health,
            "bids": bids_health,
        }
