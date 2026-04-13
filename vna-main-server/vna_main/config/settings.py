"""VNA Main Server configuration settings."""

from __future__ import annotations

import os
import sys

from pydantic_settings import BaseSettings


TESTING = os.getenv("TESTING", "false").lower() == "true" or "pytest" in os.path.basename(sys.argv[0])

TEST_DATABASE_URL = f"sqlite+aiosqlite:///./.pytest-vna-main-{os.getpid()}.db"


class Settings(BaseSettings):
    DATABASE_URL: str = (
        TEST_DATABASE_URL
        if TESTING
        else "sqlite+aiosqlite:///./vna_main.db"
    )
    DICOM_SERVER_URL: str = "http://localhost:8042"
    BIDS_SERVER_URL: str = "http://localhost:8080"
    VNA_API_KEY: str | None = None
    BIDS_SERVER_API_KEY: str | None = None
    DICOM_SERVER_USER: str | None = None
    DICOM_SERVER_PASSWORD: str | None = None

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True
    CACHE_TTL: int = 300
    CACHE_PREFIX: str = "vna:"
    REDIS_CONNECTION_TIMEOUT: int = 5

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    REQUIRE_AUTH: bool = True

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"  # "text" or "json"

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()

if settings.REQUIRE_AUTH and not settings.VNA_API_KEY:
    raise RuntimeError(
        "VNA_API_KEY environment variable must be set when REQUIRE_AUTH=true. "
        "Set VNA_API_KEY or set REQUIRE_AUTH=false (development only)."
    )
