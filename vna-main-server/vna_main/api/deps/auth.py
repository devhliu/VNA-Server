"""Authentication dependencies for the VNA main API."""

from __future__ import annotations

import hmac
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vna_main.config import settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_vna_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    """Require a bearer token when API key auth is enabled."""
    if not settings.VNA_API_KEY and not settings.REQUIRE_AUTH:
        logger.warning("Authentication is disabled (no VNA_API_KEY set and REQUIRE_AUTH=false)")
        return

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing bearer token")

    if settings.VNA_API_KEY and not hmac.compare_digest(credentials.credentials, settings.VNA_API_KEY):
        raise _unauthorized("Invalid API token")

