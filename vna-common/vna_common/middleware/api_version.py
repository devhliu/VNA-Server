"""API versioning header middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

API_VERSION_HEADER = "X-API-Version"


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Inject API version header into every response."""

    def __init__(self, app, version: str = "v1"):
        super().__init__(app)
        self.version = version

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response: Response = await call_next(request)
        response.headers[API_VERSION_HEADER] = self.version
        return response
