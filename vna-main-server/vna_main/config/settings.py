"""VNA Main Server configuration settings."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


TESTING = os.getenv("TESTING", "false").lower() == "true" or "pytest" in os.path.basename(sys.argv[0])

TEST_DATABASE_URL = f"sqlite+aiosqlite:///./.pytest-vna-main-{os.getpid()}.db"


@dataclass
class Settings:
    DATABASE_URL: str = field(
        default_factory=lambda: (
            TEST_DATABASE_URL
            if TESTING
            else os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./vna_main.db")
        )
    )
    DICOM_SERVER_URL: str = field(default_factory=lambda: os.getenv("DICOM_SERVER_URL", "http://localhost:8042"))
    BIDS_SERVER_URL: str = field(default_factory=lambda: os.getenv("BIDS_SERVER_URL", "http://localhost:8080"))
    VNA_API_KEY: str | None = field(default_factory=lambda: os.getenv("VNA_API_KEY"))
    BIDS_SERVER_API_KEY: str | None = field(default_factory=lambda: os.getenv("BIDS_SERVER_API_KEY"))
    DICOM_SERVER_USER: str | None = field(default_factory=lambda: os.getenv("DICOM_SERVER_USER"))
    DICOM_SERVER_PASSWORD: str | None = field(default_factory=lambda: os.getenv("DICOM_SERVER_PASSWORD"))
     
    REDIS_URL: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    REDIS_ENABLED: bool = field(default_factory=lambda: os.getenv("REDIS_ENABLED", "true").lower() == "true")
    CACHE_TTL: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL", "300")))
    CACHE_PREFIX: str = field(default_factory=lambda: os.getenv("CACHE_PREFIX", "vna:"))
    REDIS_CONNECTION_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("REDIS_CONNECTION_TIMEOUT", "5")))
     
    DB_POOL_SIZE: int = field(default_factory=lambda: int(os.getenv("DB_POOL_SIZE", "10")))
    DB_MAX_OVERFLOW: int = field(default_factory=lambda: int(os.getenv("DB_MAX_OVERFLOW", "20")))
    DB_POOL_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("DB_POOL_TIMEOUT", "30")))
    DB_POOL_RECYCLE: int = field(default_factory=lambda: int(os.getenv("DB_POOL_RECYCLE", "3600")))
     
    REQUIRE_AUTH: bool = field(default_factory=lambda: os.getenv("REQUIRE_AUTH", "true").lower() == "true")
     
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    LOG_FORMAT: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "text"))  # "text" or "json"


settings = Settings()

if settings.REQUIRE_AUTH and not settings.VNA_API_KEY:
    raise RuntimeError(
        "VNA_API_KEY environment variable must be set when REQUIRE_AUTH=true. "
        "Set VNA_API_KEY or set REQUIRE_AUTH=false (development only)."
    )
