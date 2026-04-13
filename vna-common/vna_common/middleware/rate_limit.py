"""Rate limiting middleware using an in-memory sliding window."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Default: 100 requests per 60 seconds per client IP
_DEFAULT_LIMIT = 100
_DEFAULT_WINDOW = 60


class _SlidingWindow:
    """Thread-safe sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window

        with self._lock:
            # Prune old timestamps
            if key in self._buckets:
                self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

            remaining = self.max_requests - len(self._buckets[key])
            if remaining <= 0:
                # Find when the oldest request in window expires
                oldest = min(self._buckets[key])
                retry_after = int(oldest - cutoff) + 1
                return False, max(0, retry_after)

            self._buckets[key].append(now)
            return True, remaining - 1


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting with configurable limits.

    Skips health, docs, and internal endpoints.
    """

    def __init__(
        self,
        app,
        max_requests: int = _DEFAULT_LIMIT,
        window_seconds: int = _DEFAULT_WINDOW,
    ):
        super().__init__(app)
        self._limiter = _SlidingWindow(max_requests, window_seconds)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bypass rate limiting during tests
        from vna_main.config.settings import TESTING
        if TESTING:
            return await call_next(request)

        path = request.url.path

        # Skip non-API paths and health/docs
        if path in ("/", "/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)
        if path.startswith("/static"):
            return await call_next(request)
        if path.startswith("/v1/health") or path.startswith("/v1/internal"):
            return await call_next(request)

        # Use X-Forwarded-For or client IP
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        allowed, info = self._limiter.is_allowed(client_ip)

        response: Response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(_DEFAULT_LIMIT)
        if isinstance(info, int) and info >= 0:
            response.headers["X-RateLimit-Remaining"] = str(info)
        if not allowed:
            response.headers["Retry-After"] = str(info)
            logger.warning("Rate limit exceeded for %s on %s", client_ip, path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "too_many_requests",
                    "detail": "Rate limit exceeded. Please retry later.",
                },
                headers=dict(response.headers),
            )

        return response
