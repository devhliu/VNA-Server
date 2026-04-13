"""Cache service for VNA Main Server with Redis backend."""

from __future__ import annotations

import json
import hashlib
import logging
from datetime import timedelta
from typing import Any, Callable, TypeVar, ParamSpec

from vna_main.config import settings

P = ParamSpec("P")
T = TypeVar("T")

_cache_backend: CacheBackend | None = None

logger = logging.getLogger(__name__)


class CacheBackend:
    """Abstract cache backend interface."""
    
    async def get(self, key: str) -> Any | None:
        raise NotImplementedError
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        raise NotImplementedError
    
    async def delete(self, key: str) -> bool:
        raise NotImplementedError
    
    async def exists(self, key: str) -> bool:
        raise NotImplementedError
    
    async def clear_pattern(self, pattern: str) -> int:
        raise NotImplementedError
    
    async def close(self) -> None:
        raise NotImplementedError


class RedisCacheBackend(CacheBackend):
    """Redis-based cache backend."""
    
    def __init__(self, url: str, prefix: str = "vna:"):
        self._url = url
        self._prefix = prefix
        self._redis: Any | None = None
    
    @property
    def redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self._url, decode_responses=True)
        return self._redis
    
    def _make_key(self, key: str) -> str:
        return f"{self._prefix}{key}"
    
    async def get(self, key: str) -> Any | None:
        full_key = self._make_key(key)
        value = await self.redis.get(full_key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        full_key = self._make_key(key)
        ttl = ttl or settings.CACHE_TTL
        if isinstance(value, (dict, list, tuple)):
            value = json.dumps(value, default=str)
        result = await self.redis.setex(full_key, ttl, value)
        return bool(result)
    
    async def delete(self, key: str) -> bool:
        full_key = self._make_key(key)
        result = await self.redis.delete(full_key)
        return result > 0
    
    async def exists(self, key: str) -> bool:
        full_key = self._make_key(key)
        return bool(await self.redis.exists(full_key))
    
    async def clear_pattern(self, pattern: str) -> int:
        full_pattern = self._make_key(pattern)
        keys = []
        async for key in self.redis.scan_iter(match=full_pattern):
            keys.append(key)
        if keys:
            return await self.redis.delete(*keys)
        return 0
    
    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend for development/testing."""
    
    def __init__(self, prefix: str = "vna:"):
        self._prefix = prefix
        self._store: dict[str, tuple[Any, float]] = {}
    
    def _make_key(self, key: str) -> str:
        return f"{self._prefix}{key}"
    
    async def get(self, key: str) -> Any | None:
        import time
        full_key = self._make_key(key)
        entry = self._store.get(full_key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[full_key]
            return None
        return value
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        import time
        full_key = self._make_key(key)
        ttl = ttl or settings.CACHE_TTL
        expires_at = time.time() + ttl
        self._store[full_key] = (value, expires_at)
        return True
    
    async def delete(self, key: str) -> bool:
        full_key = self._make_key(key)
        if full_key in self._store:
            del self._store[full_key]
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        import time
        full_key = self._make_key(key)
        entry = self._store.get(full_key)
        if entry is None:
            return False
        _, expires_at = entry
        if time.time() > expires_at:
            del self._store[full_key]
            return False
        return True
    
    async def clear_pattern(self, pattern: str) -> int:
        import fnmatch
        full_pattern = self._make_key(pattern)
        keys_to_delete = [
            k for k in self._store
            if fnmatch.fnmatch(k, full_pattern)
        ]
        for key in keys_to_delete:
            del self._store[key]
        return len(keys_to_delete)
    
    async def close(self) -> None:
        self._store.clear()


def get_cache() -> CacheBackend:
    """Get or create the cache backend instance."""
    global _cache_backend
    if _cache_backend is None:
        if settings.REDIS_ENABLED:
            _cache_backend = RedisCacheBackend(
                url=settings.REDIS_URL,
                prefix=settings.CACHE_PREFIX,
            )
        else:
            _cache_backend = MemoryCacheBackend(prefix=settings.CACHE_PREFIX)
    return _cache_backend


async def close_cache() -> None:
    """Close the cache backend."""
    global _cache_backend
    if _cache_backend:
        await _cache_backend.close()
        _cache_backend = None


def make_cache_key(*args: Any, **kwargs: Any) -> str:
    """Generate a cache key from arguments."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = ":".join(key_parts)
    return hashlib.sha256(key_string.encode()).hexdigest()


def cached(
    key_prefix: str,
    ttl: int | None = None,
    key_builder: Callable[..., str] | None = None,
):
    """Decorator for caching function results."""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            cache = get_cache()
            
            if key_builder:
                cache_key = f"{key_prefix}:{key_builder(*args, **kwargs)}"
            else:
                cache_key = f"{key_prefix}:{make_cache_key(*args, **kwargs)}"
            
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            result = await func(*args, **kwargs)
            
            if result is not None:
                await cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


class CacheKeys:
    """Standard cache key patterns."""
    
    RESOURCE = "resource:{resource_id}"
    RESOURCE_LIST = "resources:list:{page}:{limit}"
    PATIENT = "patient:{patient_ref}"
    PATIENT_RESOURCES = "patient:{patient_ref}:resources"
    LABELS = "labels:{resource_id}"
    LABEL_HISTORY = "labels:history:{resource_id}"
    QUERY_RESULT = "query:{query_hash}"
    DICOM_STATS = "dicom:stats"
    BIDS_STATS = "bids:stats"
    HEALTH_STATUS = "health:status"
    
    @classmethod
    def resource_key(cls, resource_id: str) -> str:
        return cls.RESOURCE.format(resource_id=resource_id)
    
    @classmethod
    def patient_key(cls, patient_ref: str) -> str:
        return cls.PATIENT.format(patient_ref=patient_ref)
    
    @classmethod
    def labels_key(cls, resource_id: str) -> str:
        return cls.LABELS.format(resource_id=resource_id)
    
    @classmethod
    def query_key(cls, query_hash: str) -> str:
        return cls.QUERY_RESULT.format(query_hash=query_hash)
