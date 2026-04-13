"""Request ID tracing middleware."""

from __future__ import annotations

import logging
import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-_]{1,64}
)
_MAX_REQUEST_ID_LENGTH = 64


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to every request for tracing."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_id = request.headers.get(REQUEST_ID_HEADER)
        if incoming_id and len(incoming_id) <= _MAX_REQUEST_ID_LENGTH and _REQUEST_ID_PATTERN.match(incoming_id):
            request_id = incoming_id
        else:
            request_id = f"req-{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
