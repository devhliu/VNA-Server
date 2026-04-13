"""BIDS Server Configuration with Multi-Datacenter Support."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


class DatacenterConfig:
    """Configuration for a single datacenter."""
    
    def __init__(
        self,
        id: str,
        name: str,
        region: str,
        endpoint: str,
        priority: int = 0,
        is_primary: bool = False,
        is_active: bool = True,
    ):
        self.id = id
        self.name = name
        self.region = region
        self.endpoint = endpoint
        self.priority = priority
        self.is_primary = is_primary
        self.is_active = is_active


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vna:vna@localhost:5432/bidsserver"
    database_echo: bool = False

    bids_root: str = "/bids_data"
    upload_temp_dir: str = "/tmp/bids_uploads"

    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    bids_api_key: str | None = None

    max_upload_size: int = 10_737_418_240
    chunk_size: int = 10_485_760

    hash_algorithm: str = "sha256"

    enable_background_worker: bool = True
    worker_poll_interval_seconds: float = 2.0
    worker_reclaim_interval_seconds: float = 60.0
    worker_heartbeat_seconds: float = 30.0
    stale_task_seconds: int = 300
    task_max_attempts: int = 4
    webhook_max_attempts: int = 6
    webhook_timeout_seconds: float = 10.0

    datacenter_id: str = "dc-default"
    datacenter_name: str = "Default Datacenter"
    datacenter_region: str = "default"
    is_primary_datacenter: bool = True
    
    replication_enabled: bool = False
    replication_endpoints: str = ""
    replication_sync_interval: int = 300
    replication_batch_size: int = 100

    cors_origins: List[str] = []

    require_auth: bool = True

    log_level: str = "INFO"
    log_format: str = "text"  # "text" or "json"

    model_config = {"env_file": "config/settings.env", "case_sensitive": False}

    def get_datacenter_config(self) -> DatacenterConfig:
        return DatacenterConfig(
            id=self.datacenter_id,
            name=self.datacenter_name,
            region=self.datacenter_region,
            endpoint=f"http://{self.host}:{self.port}",
            is_primary=self.is_primary_datacenter,
        )
    
    def get_replication_endpoints(self) -> list[str]:
        if not self.replication_endpoints:
            return []
        return [
            ep.strip()
            for ep in self.replication_endpoints.split(",")
            if ep.strip()
        ]


settings = Settings()

_cors_env = os.environ.get("CORS_ORIGINS")
if _cors_env:
    settings.cors_origins = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]

if settings.require_auth and not settings.bids_api_key:
    raise RuntimeError(
        "BIDS_API_KEY environment variable must be set when require_auth=true. "
        "Set BIDS_API_KEY or set REQUIRE_AUTH=false (development only)."
    )

for attr in ("bids_root", "upload_temp_dir"):
    raw_path = Path(getattr(settings, attr))
    try:
        raw_path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        setattr(settings, attr, tempfile.mkdtemp(prefix="bids_"))
