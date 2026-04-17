"""Pydantic schemas for BIDS Server API."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ===== Subjects =====
class SubjectCreate(BaseModel):
    subject_id: str
    patient_ref: Optional[str] = None
    hospital_ids: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class SubjectUpdate(BaseModel):
    patient_ref: Optional[str] = None
    hospital_ids: Optional[dict] = None
    metadata: Optional[dict] = None


class SubjectResponse(BaseModel):
    subject_id: str
    patient_ref: Optional[str]
    hospital_ids: dict
    metadata: dict = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


# ===== Sessions =====
class SessionCreate(BaseModel):
    session_id: str
    subject_id: str
    session_label: Optional[str] = None
    scan_date: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    session_label: Optional[str] = None
    scan_date: Optional[datetime] = None
    metadata: Optional[dict] = None


class SessionResponse(BaseModel):
    session_id: str
    subject_id: str
    session_label: Optional[str]
    scan_date: Optional[datetime]
    metadata: dict = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


# ===== Resources / Objects =====
class ResourceCreate(BaseModel):
    subject_id: Optional[str] = None
    session_id: Optional[str] = None
    modality: str
    file_name: str
    source: str = "user_upload"
    dicom_ref: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class ResourceResponse(BaseModel):
    resource_id: str
    subject_id: Optional[str]
    session_id: Optional[str]
    modality: str
    bids_path: str
    file_name: str
    file_type: Optional[str]
    file_size: int
    content_hash: Optional[str]
    source: str
    dicom_ref: Optional[str]
    metadata: dict = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class RelationshipUpdate(BaseModel):
    parent_refs: list[str] = Field(default_factory=list)
    children_refs: list[str] = Field(default_factory=list)
    dicom_ref: Optional[str] = None
    same_subject: list[str] = Field(default_factory=list)


class RelationshipResponse(RelationshipUpdate):
    resource_id: str


# ===== Labels =====
class LabelSet(BaseModel):
    labels: dict
    level: str = "file"
    target_path: Optional[str] = None


class LabelPatch(BaseModel):
    add: dict = Field(default_factory=dict)
    remove: list[str] = Field(default_factory=list)


class LabelResponse(BaseModel):
    id: int
    resource_id: Optional[str]
    level: str
    target_path: Optional[str]
    tag_key: str
    tag_value: Optional[str]
    tagged_by: Optional[str]
    tagged_at: datetime

    model_config = {"from_attributes": True}


# ===== Annotations =====
class AnnotationCreate(BaseModel):
    resource_id: str
    ann_type: str
    label: Optional[str] = None
    data: dict
    confidence: Optional[float] = None
    created_by: Optional[str] = None


class AnnotationUpdate(BaseModel):
    label: Optional[str] = None
    data: Optional[dict] = None
    confidence: Optional[float] = None


class AnnotationResponse(BaseModel):
    annotation_id: str
    resource_id: str
    ann_type: str
    label: Optional[str]
    data: dict
    confidence: Optional[float]
    created_by: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Upload =====
class UploadInitRequest(BaseModel):
    file_name: str
    file_size: int
    chunk_size: Optional[int] = None
    modality: str
    subject_id: Optional[str] = None
    session_id: Optional[str] = None
    source: str = "user_upload"
    labels: Optional[dict] = None
    metadata: Optional[dict] = None
    dicom_ref: Optional[str] = None


class UploadInitResponse(BaseModel):
    upload_id: str
    chunk_size: int
    total_chunks: int


class UploadStatusResponse(BaseModel):
    upload_id: str
    file_name: str
    file_size: int
    bytes_received: int
    chunks_received: list[int]
    status: str  # uploading | completed | failed


# ===== Tasks =====
class TaskCreate(BaseModel):
    action: str
    resource_ids: list[str] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)
    callback_url: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    action: str
    resource_ids: list
    params: dict
    status: str
    progress: float
    result: Optional[dict]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ===== Webhooks =====
class WebhookCreate(BaseModel):
    name: Optional[str] = None
    url: str
    events: list[str]
    secret: Optional[str] = None
    filters: dict = Field(default_factory=dict)


class WebhookResponse(BaseModel):
    webhook_id: str
    name: Optional[str]
    url: str
    events: list
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Modality =====
class ModalityCreate(BaseModel):
    modality_id: str
    directory: str
    description: Optional[str] = None
    extensions: list[str]
    required_files: list[str] = Field(default_factory=lambda: ["json"])
    category: str = "other"


class ModalityResponse(BaseModel):
    modality_id: str
    directory: str
    description: Optional[str]
    extensions: list
    required_files: list
    category: str
    is_system: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Verify =====
class VerifyRequest(BaseModel):
    target: str = Field(default="all", description="all | specific resource_id or bids_path")
    check_hash: bool = Field(default=False, description="Verify file content hash")
    repair: bool = Field(default=False, description="Auto-repair database from filesystem")


class VerifyResponse(BaseModel):
    total_checked: int
    ok: int
    issues: int
    repaired: int
    results: list["VerifyResult"]


class VerifyResult(BaseModel):
    resource_id: Optional[str] = None
    bids_path: str
    status: str
    detail: Optional[str] = None


# ===== Rebuild =====
class RebuildRequest(BaseModel):
    target: str = Field(default="all", description="all | subject_id | session_id")
    clear_existing: bool = Field(default=False, description="Clear existing DB entries before rebuild")


class RebuildResponse(BaseModel):
    target: str
    subjects_found: int
    sessions_found: int
    resources_found: int
    labels_found: int = 0
    duration_seconds: float


# ===== Query =====
class QueryRequest(BaseModel):
    subject_id: Optional[str] = None
    session_id: Optional[str] = None
    modality: Optional[list[str]] = None
    source: Optional[list[str]] = None
    file_type: Optional[list[str]] = None
    dicom_ref: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: Optional[dict] = None
    time_range: Optional[dict] = None
    labels: Optional[dict] = None
    search: Optional[str] = None
    sort: Optional[list[dict]] = None
    limit: int = 100
    offset: int = 0


class QueryResponse(BaseModel):
    total: int
    resources: list[ResourceResponse]
