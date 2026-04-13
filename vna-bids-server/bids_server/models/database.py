"""SQLAlchemy ORM models - database agnostic."""

import logging
import uuid
import os
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    BigInteger,
    String,
    Text,
    Index,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship

logger = logging.getLogger(__name__)

# Determine if using PostgreSQL
_IS_PG = "postgresql" in os.environ.get("DATABASE_URL", "")

# Use JSONB for PostgreSQL, JSON for others
JSON_TYPE = JSON  # Works for both PG and SQLite

# PG-only tsvector column type; falls back to Text for SQLite
if _IS_PG:
    from sqlalchemy.dialects.postgresql import TSVECTOR

    _SEARCH_VECTOR_TYPE = TSVECTOR
else:
    _SEARCH_VECTOR_TYPE = Text


class Base(DeclarativeBase):
    pass  # noqa: B024 — empty base class is intentional for SQLAlchemy


def _uuid() -> str:
    return uuid.uuid4().hex[:20]


class Subject(Base):
    __tablename__ = "subjects"

    subject_id = Column(String(64), primary_key=True)
    patient_ref = Column(String(128), nullable=True)
    hospital_ids = Column(JSON_TYPE, default=dict)
    metadata_ = Column("metadata", JSON_TYPE, default=dict)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sessions = relationship(
        "Session", back_populates="subject", cascade="all, delete-orphan"
    )
    resources = relationship(
        "Resource", back_populates="subject", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String(128), primary_key=True)
    subject_id = Column(String(64), ForeignKey("subjects.subject_id", ondelete="CASCADE"), nullable=False)
    session_label = Column(String(64))
    scan_date = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSON_TYPE, default=dict)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    subject = relationship("Subject", back_populates="sessions")
    resources = relationship(
        "Resource", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sessions_subject", "subject_id"),
        Index("idx_sessions_composite", "subject_id", "session_label"),
    )


class Resource(Base):
    __tablename__ = "resources"

    resource_id = Column(String(64), primary_key=True, default=lambda: f"res-{_uuid()}")
    subject_id = Column(
        String(64), ForeignKey("subjects.subject_id", ondelete="CASCADE", deferrable=True), nullable=True
    )
    session_id = Column(
        String(128), ForeignKey("sessions.session_id", ondelete="CASCADE", deferrable=True), nullable=True
    )
    modality = Column(String(32), nullable=False, index=True)
    bids_path = Column(Text, nullable=False, unique=True)
    file_name = Column(String(256), nullable=False)
    file_type = Column(String(32))
    file_size = Column(BigInteger, default=0)
    content_hash = Column(String(128))
    source = Column(String(32), default="user_upload")
    dicom_ref = Column(String(256), nullable=True)
    metadata_ = Column("metadata", JSON_TYPE, default=dict)
    search_vector = Column("search_vector", _SEARCH_VECTOR_TYPE, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    subject = relationship("Subject", back_populates="resources")
    session = relationship("Session", back_populates="resources")
    labels = relationship(
        "Label", back_populates="resource", cascade="all, delete-orphan"
    )
    annotations = relationship(
        "Annotation", back_populates="resource", cascade="all, delete-orphan"
    )
    processing_logs = relationship(
        "ProcessingLog", back_populates="resource", cascade="all, delete-orphan"
    )
    relationship_record = relationship(
        "Relationship",
        back_populates="resource",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_resources_subject", "subject_id"),
        Index("idx_resources_session", "session_id"),
        Index("idx_resources_modality", "modality"),
        Index("idx_resources_hash", "content_hash"),
        Index("idx_resources_composite", "subject_id", "session_id", "modality"),
    )


class Label(Base):
    __tablename__ = "labels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        String(64),
        ForeignKey("resources.resource_id", ondelete="CASCADE"),
        nullable=False,
    )
    level = Column(String(16), nullable=False)
    target_path = Column(Text)
    tag_key = Column(String(128), nullable=False)
    tag_value = Column(Text)
    tagged_by = Column(String(128))
    tagged_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    resource = relationship("Resource", back_populates="labels")

    __table_args__ = (
        Index("idx_labels_resource", "resource_id"),
        Index("idx_labels_key", "tag_key"),
        Index("idx_labels_value", "tag_value"),
        Index("idx_labels_target", "target_path"),
    )


class Annotation(Base):
    __tablename__ = "annotations"

    annotation_id = Column(
        String(64), primary_key=True, default=lambda: f"ann-{_uuid()}"
    )
    resource_id = Column(
        String(64),
        ForeignKey("resources.resource_id", ondelete="CASCADE"),
        nullable=False,
    )
    ann_type = Column(String(32), nullable=False)
    label = Column(String(128))
    data = Column(JSON_TYPE, nullable=False)
    confidence = Column(Float, nullable=True)
    created_by = Column(String(128))
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    resource = relationship("Resource", back_populates="annotations")

    __table_args__ = (
        Index("idx_annotations_resource", "resource_id"),
        Index("idx_annotations_type", "ann_type"),
    )


class ProcessingLog(Base):
    __tablename__ = "processing_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        String(64),
        ForeignKey("resources.resource_id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline = Column(String(128))
    input_resources = Column(JSON_TYPE, default=list)
    params = Column(JSON_TYPE, default=dict)
    executed_by = Column(String(128))
    executed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    resource = relationship("Resource", back_populates="processing_logs")

    __table_args__ = (Index("idx_processing_resource", "resource_id"),)


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        String(64),
        ForeignKey("resources.resource_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    parent_refs = Column(JSON_TYPE, default=list)
    children_refs = Column(JSON_TYPE, default=list)
    dicom_ref = Column(String(256), nullable=True)
    same_subject = Column(JSON_TYPE, default=list)

    resource = relationship("Resource", back_populates="relationship_record")


class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(String(64), primary_key=True, default=lambda: f"tsk-{_uuid()}")
    action = Column(String(64), nullable=False)
    resource_ids = Column(JSON_TYPE, default=list)
    params = Column(JSON_TYPE, default=dict)
    status = Column(String(16), default="queued")
    progress = Column(Float, default=0)
    result = Column(JSON_TYPE, nullable=True)
    error = Column(Text, nullable=True)
    callback_url = Column(Text, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=4)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_due", "status", "next_attempt_at"),
    )


class Webhook(Base):
    __tablename__ = "webhooks"

    webhook_id = Column(String(64), primary_key=True, default=lambda: f"whk-{_uuid()}")
    name = Column(String(128))
    url = Column(Text, nullable=False)
    events = Column(JSON_TYPE, nullable=False)
    secret = Column(String(256), nullable=True)
    filters = Column(JSON_TYPE, default=dict)
    active = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    delivery_id = Column(String(64), primary_key=True, default=lambda: f"whd-{_uuid()}")
    webhook_id = Column(String(64), ForeignKey("webhooks.webhook_id", ondelete="CASCADE"), nullable=True)
    target_url = Column(Text, nullable=False)
    secret = Column(String(256), nullable=True)
    event = Column(String(128), nullable=False)
    payload = Column(JSON_TYPE, nullable=False)
    status = Column(String(16), nullable=False, default="queued")
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=6)
    response_status = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_webhook_deliveries_status", "status"),
        Index("idx_webhook_deliveries_due", "status", "next_attempt_at"),
        Index("idx_webhook_deliveries_webhook_id", "webhook_id"),
    )


class BidsDataset(Base):
    __tablename__ = "bids_datasets"

    dataset_id = Column(String(64), primary_key=True, default=lambda: f"ds-{_uuid()}")
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    dataset_path = Column(Text, nullable=False)
    version = Column(String(32), default="1.0.0")
    is_valid = Column(Boolean, default=False)
    validation_report = Column(JSON_TYPE, nullable=True)
    subject_count = Column(Integer, default=0)
    session_count = Column(Integer, default=0)
    total_size = Column(BigInteger, default=0)
    created_by = Column(String(128))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    sessions = relationship("BidsSession", back_populates="dataset", cascade="all, delete-orphan")


class BidsSession(Base):
    __tablename__ = "bids_sessions"

    session_id = Column(String(128), primary_key=True)
    dataset_id = Column(String(64), ForeignKey("bids_datasets.dataset_id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(String(64), nullable=True)
    session_label = Column(String(64), nullable=True)
    scan_date = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSON_TYPE, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    dataset = relationship("BidsDataset", back_populates="sessions")


class ConversionJob(Base):
    __tablename__ = "conversion_jobs"

    job_id = Column(String(64), primary_key=True, default=lambda: f"cj-{_uuid()}")
    task_id = Column(String(64), ForeignKey("tasks.task_id", ondelete="SET NULL"), nullable=True)
    input_path = Column(Text, nullable=True)
    output_path = Column(Text, nullable=True)
    config = Column(JSON_TYPE, default=dict)
    status = Column(String(16), default="pending")  # pending, running, completed, failed
    progress = Column(Float, default=0)
    result = Column(JSON_TYPE, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    task = relationship("Task")
    __table_args__ = (Index("idx_conversion_jobs_status", "status"), Index("idx_conversion_jobs_task_id", "task_id"))


class ModalityRegistry(Base):
    __tablename__ = "modalities"

    modality_id = Column(String(64), primary_key=True)
    directory = Column(String(64), nullable=False)
    description = Column(Text)
    extensions = Column(JSON_TYPE, nullable=False)
    required_files = Column(JSON_TYPE, default=lambda: ["json"])
    category = Column(String(32), default="other")
    is_system = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
