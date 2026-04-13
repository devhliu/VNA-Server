"""Pydantic v2 models for VNA Main Server SDK."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    """Data source type."""

    DICOM = "dicom"
    BIDS = "bids"


class DataType(str, Enum):
    """Resource data type."""

    IMAGING = "imaging"
    DERIVATIVE = "derivative"
    BIDS_RAW = "bids_raw"
    BIDS_DERIV = "bids_deriv"


class Label(BaseModel):
    """Label/tag model."""

    model_config = ConfigDict(frozen=True)

    key: str
    value: Optional[str] = None


class Resource(BaseModel):
    """Resource model - unified view of DICOM + BIDS data."""

    model_config = ConfigDict(str_strip_whitespace=True)

    resource_id: str
    patient_ref: str
    source_type: SourceType
    data_type: DataType = DataType.IMAGING
    dicom_study_uid: Optional[str] = None
    dicom_series_uid: Optional[str] = None
    bids_path: Optional[str] = None
    bids_subject: Optional[str] = None
    bids_session: Optional[str] = None
    bids_datatype: Optional[str] = None
    labels: list[Label] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Patient(BaseModel):
    """Patient model with resource mappings."""

    model_config = ConfigDict(str_strip_whitespace=True)

    patient_ref: str
    hospital_id: Optional[str] = None
    source: Optional[str] = None
    resource_count: int = 0
    resources: list[Resource] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QueryResult(BaseModel):
    """Query result model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    total: int = 0
    limit: int = 50
    offset: int = 0
    resources: list[Resource] = Field(default_factory=list)


class SyncEvent(BaseModel):
    """Sync event model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    event_id: str
    source: str
    event_type: str
    status: str
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SyncStatus(BaseModel):
    """Sync status model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    dicom: dict[str, Any] = Field(default_factory=dict)
    bids: dict[str, Any] = Field(default_factory=dict)
    last_sync: Optional[datetime] = None
    events: list[SyncEvent] = Field(default_factory=list)


class HealthStatus(BaseModel):
    """Health status model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    status: str = "ok"
    version: str = ""
    database: str = "ok"
    uptime_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ServerRegistration(BaseModel):
    """Server registration model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    server_type: str
    url: str
    name: str
    server_id: Optional[str] = None
    registered_at: Optional[datetime] = None


class BatchLabelOperation(BaseModel):
    """Batch label operation model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    resource_id: str
    operation: str  # "set", "add", "remove"
    labels: Optional[dict[str, Optional[str]]] = None
    add: Optional[dict[str, Optional[str]]] = None
    remove: Optional[list[str]] = None


class TagInfo(BaseModel):
    """Tag info with count."""

    model_config = ConfigDict(frozen=True)

    key: str
    count: int = 0


class WebhookDelivery(BaseModel):
    """Webhook delivery record."""

    model_config = ConfigDict(str_strip_whitespace=True)

    delivery_id: str
    webhook_id: int
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    attempts: int = 1
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None


class WebhookSubscription(BaseModel):
    """Webhook subscription model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: int
    url: str
    events: list[str]
    secret: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


class WebhookStats(BaseModel):
    """Webhook statistics model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    total: int = 0
    enabled: int = 0
    disabled: int = 0
    event_counts: dict[str, int] = Field(default_factory=dict)
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0


class LabelHistoryEntry(BaseModel):
    """Label history entry."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: int
    resource_id: str
    tag_key: str
    tag_value: str
    tag_type: str = "custom"
    action: str  # created | updated | deleted
    tagged_by: Optional[str] = None
    tagged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LabelHistoryResult(BaseModel):
    """Label history query result."""

    model_config = ConfigDict(str_strip_whitespace=True)

    total: int = 0
    limit: int = 50
    offset: int = 0
    items: list[LabelHistoryEntry] = Field(default_factory=list)


class PatientSyncStatus(BaseModel):
    """Patient sync status from DICOM/BIDS to VNA."""

    model_config = ConfigDict(str_strip_whitespace=True)

    total_patients: int = 0
    dicom_patients: int = 0
    bids_patients: int = 0
    total_resources: int = 0
    mapped_resources: int = 0
    last_sync: Optional[datetime] = None
