"""Rate limiting middleware using Redis-backed sliding window."""

from __future__ import annotations

import logging
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from vna_main.config.settings import TESTING
from vna_main.services.cache_service import get_cache

logger = logging.getLogger(__name__)

# Default: 100 requests per 60 seconds per client IP
_DEFAULT_LIMIT = 100
_DEFAULT_WINDOW = 60
# Only trust X-Forwarded-For from these proxy IPs (empty = trust none)
_TRUSTED_PROXIES: set[str] = set()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting with configurable limits using Redis.

    Skips health, docs, and internal endpoints.
    """

    def __init__(
        self,
        app,
        max_requests: int = _DEFAULT_LIMIT,
        window_seconds: int = _DEFAULT_WINDOW,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bypass rate limiting during tests
        if TESTING:
            return await call_next(request)

        path = request.url.path

        # Skip non-API paths and health/docs
        if path in ("/", "/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)
        if path.startswith("/static"):
            return await call_next(request)
        if path.startswith("/api/v1/health") or path.startswith("/api/v1/internal"):
            return await call_next(request)

        # Use X-Forwarded-For only from trusted proxies, otherwise use client IP
        client_ip = ""
        direct_ip = request.client.host if request.client else "unknown"
        if _TRUSTED_PROXIES and direct_ip in _TRUSTED_PROXIES:
            client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = direct_ip

        # Check rate limit using Redis
        cache = get_cache()
        
        key = f"rate_limit:{client_ip}"
        now = time.time()
        window_start = now - self.window
        
        # Use Redis pipeline to batch commands into a single round-trip
        try:
            async with cache.redis.pipeline() as pipe:
                await pipe.zadd(key, {str(now): now})
                await pipe.zremrangebyscore(key, 0, window_start)
                await pipe.expire(key, int(self.window))
                await pipe.zcard(key)
                results = await pipe.execute()
            
            count = results[-1]
        except Exception as e:
            # Fail-open: if Redis is down, allow the request
            logger.warning("Rate limit Redis error, allowing request: %s", e)
            response: Response = await call_next(request)
            return response
        
        if count > self.max_requests:
            # Calculate retry after (time until oldest request expires)
            try:
                oldest = await cache.redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = oldest[0][1]
                    retry_after = int(oldest_time + self.window - now) + 1
                else:
                    retry_after = self.window
            except Exception:
                retry_after = self.window
                
            logger.warning("Rate limit exceeded for %s on %s", client_ip, path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "too_many_requests",
                    "detail": "Rate limit exceeded. Please retry later.",
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(retry_after),
                },
            )
        
        response: Response = await call_next(request)
        
        # Add rate limit headers
        remaining = max(0, self.max_requests - count)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
