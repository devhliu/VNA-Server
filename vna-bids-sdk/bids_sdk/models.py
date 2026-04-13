"""Pydantic models for BIDS Server SDK."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Label(BaseModel):
    """Label/tag applied to a resource."""
    key: str
    value: Optional[str] = None
    tagged_by: Optional[str] = None
    tagged_at: Optional[datetime] = None


class Resource(BaseModel):
    """A BIDS resource (file)."""
    model_config = ConfigDict(populate_by_name=True)
    resource_id: str = ""
    subject_id: Optional[str] = None
    session_id: Optional[str] = None
    modality: str = "other"
    bids_path: str = ""
    file_name: str = ""
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    content_hash: Optional[str] = None
    source: str = "user_upload"
    dicom_ref: Optional[str] = None
    metadata_: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QueryResult(BaseModel):
    """Query response."""
    total: int
    resources: List[Resource] = Field(default_factory=list)


class Annotation(BaseModel):
    """Annotation on a resource."""
    model_config = ConfigDict(populate_by_name=True)
    annotation_id: str = ""
    resource_id: str = ""
    type: str = ""
    label: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


class Subject(BaseModel):
    """A BIDS subject."""
    model_config = ConfigDict(populate_by_name=True)
    subject_id: str = ""
    patient_ref: Optional[str] = None
    hospital_ids: Any = Field(default_factory=dict)
    metadata_: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Session(BaseModel):
    """A BIDS session."""
    model_config = ConfigDict(populate_by_name=True)
    session_id: str = ""
    subject_id: str = ""
    session_label: Optional[str] = None
    scan_date: Optional[datetime] = None
    metadata_: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Task(BaseModel):
    """An async task."""
    model_config = ConfigDict(populate_by_name=True)
    task_id: str = ""
    action: str = ""
    status: str = "queued"
    progress: float = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Webhook(BaseModel):
    """A webhook subscription."""
    model_config = ConfigDict(populate_by_name=True)
    webhook_id: str = ""
    name: Optional[str] = None
    url: str = ""
    events: List[str] = Field(default_factory=list)
    active: bool = True
    created_at: Optional[datetime] = None


class Modality(BaseModel):
    """A registered modality."""
    model_config = ConfigDict(populate_by_name=True)
    modality_id: str = ""
    directory: str = ""
    description: Optional[str] = None
    extensions: List[str] = Field(default_factory=list)
    category: str = "other"
    is_system: bool = False


class UploadInit(BaseModel):
    """Chunked upload initialization response."""
    upload_id: str
    chunk_size: int = 0
    total_chunks: int = 0


class VerifyResult(BaseModel):
    """Single verification result."""
    resource_id: Optional[str] = None
    bids_path: str = ""
    status: str = "ok"
    detail: Optional[str] = None


class VerifyResponse(BaseModel):
    """Verification response."""
    total_checked: int = 0
    ok: int = 0
    issues: int = 0
    repaired: int = 0
    results: List[VerifyResult] = Field(default_factory=list)


class RebuildResponse(BaseModel):
    """Rebuild response."""
    target: str = "all"
    subjects_found: int = 0
    sessions_found: int = 0
    resources_found: int = 0
    labels_found: int = 0
    duration_seconds: float = 0
