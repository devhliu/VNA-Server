"""SQLAlchemy async models for VNA Main Server."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from vna_main.config import settings


class Base(DeclarativeBase):
    pass  # noqa: B027 — DeclarativeBase requires an empty class body


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_resource_id() -> str:
    return f"res-{uuid.uuid4().hex[:12]}"


def _make_patient_ref() -> str:
    return f"pt-{uuid.uuid4().hex[:8]}"


class PatientMapping(Base):
    __tablename__ = "patient_mapping"

    patient_ref: Mapped[str] = mapped_column(String(32), primary_key=True, default=_make_patient_ref)
    hospital_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    external_system: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    resources: Mapped[list[ResourceIndex]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class ResourceIndex(Base):
    __tablename__ = "resource_index"
    __table_args__ = (
        Index("idx_resource_patient_ref", "patient_ref"),
        Index("idx_resource_dicom_study", "dicom_study_uid"),
        Index("idx_resource_bids_subject", "bids_subject_id"),
        Index("idx_resource_source_type", "source_type"),
        Index("idx_resource_composite", "patient_ref", "source_type", "data_type"),
    )

    resource_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_make_resource_id)
    patient_ref: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("patient_mapping.patient_ref", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="dicom_only"
    )  # dicom_only | bids_only | dicom_and_bids
    dicom_study_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dicom_series_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dicom_sop_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bids_subject_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bids_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bids_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(64), nullable=False, default="dicom")
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    patient: Mapped[PatientMapping | None] = relationship(back_populates="resources")
    labels: Mapped[list[Label]] = relationship(back_populates="resource", cascade="all, delete-orphan")


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("resource_index.resource_id", ondelete="CASCADE"), nullable=False
    )
    tag_key: Mapped[str] = mapped_column(String(256), nullable=False)
    tag_value: Mapped[str] = mapped_column(String(1024), nullable=False)
    tag_type: Mapped[str] = mapped_column(String(32), nullable=False, default="custom")  # system | custom | agent
    tagged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    resource: Mapped[ResourceIndex] = relationship(back_populates="labels")


class SyncEvent(Base):
    __tablename__ = "sync_events"
    __table_args__ = (
        Index("idx_sync_events_processed", "processed"),
        Index("idx_sync_events_source_db", "source_db"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_db: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"
    __table_args__ = (
        Index("idx_webhook_subscriptions_url_events", "url", "events"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    secret: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class LabelHistory(Base):
    __tablename__ = "label_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("resource_index.resource_id", ondelete="CASCADE"), nullable=False
    )
    tag_key: Mapped[str] = mapped_column(String(256), nullable=False)
    tag_value: Mapped[str] = mapped_column(String(1024), nullable=False)
    tag_type: Mapped[str] = mapped_column(String(32), nullable=False, default="custom")
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # created | updated | deleted
    tagged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"
    __table_args__ = (
        Index("idx_webhook_delivery_logs_subscription_id", "subscription_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(Integer, ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    delivery_id: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    subscription: Mapped[WebhookSubscription] = relationship(foreign_keys=[subscription_id])


class ResourceVersion(Base):
    __tablename__ = "resource_versions"
    __table_args__ = (
        Index("idx_resource_versions_resource_version", "resource_id", "version_number", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("resource_index.resource_id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    change_description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    changed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    resource: Mapped[ResourceIndex] = relationship(foreign_keys=[resource_id])


class DataSnapshot(Base):
    __tablename__ = "data_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, default=lambda: f"snap-{uuid.uuid4().hex[:12]}")
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    resource_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RoutingRule(Base):
    __tablename__ = "routing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False, default="data_type")
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    target: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: f"prj-{uuid.uuid4().hex[:12]}")
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    principal_investigator: Mapped[str | None] = mapped_column(String(256), nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    members: Mapped[list[ProjectMember]] = relationship(back_populates="project", cascade="all, delete-orphan")
    resource_links: Mapped[list[ProjectResource]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    patient_ref: Mapped[str | None] = mapped_column(String(32), ForeignKey("patient_mapping.patient_ref", ondelete="SET NULL"), nullable=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="member")  # PI, co_investigator, member, analyst
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped[Project] = relationship(back_populates="members")


class ProjectResource(Base):
    __tablename__ = "project_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(32), ForeignKey("resource_index.resource_id", ondelete="CASCADE"), nullable=False)
    added_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped[Project] = relationship(back_populates="resource_links")


class TreatmentEvent(Base):
    __tablename__ = "treatment_events"
    __table_args__ = (
        Index("idx_treatment_events_patient_ref", "patient_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_ref: Mapped[str | None] = mapped_column(String(32), ForeignKey("patient_mapping.patient_ref", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # surgery, chemotherapy, radiation, immunotherapy, follow_up
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    facility: Mapped[str | None] = mapped_column(String(256), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_log_action", "action"),
        Index("idx_audit_log_resource_type", "resource_type"),
        Index("idx_audit_log_actor", "actor"),
        Index("idx_audit_log_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # create, update, delete, sync, login
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# Engine / session factory (async)
# ---------------------------------------------------------------------------

_engine = None
_session_factory = None
_initialized_urls: set[str] = set()
_init_lock = asyncio.Lock()


def get_engine(db_url: str | None = None):
    global _engine
    if _engine is None or db_url is not None:
        url = db_url or settings.DATABASE_URL
        engine_kwargs = {"echo": False}
        if "sqlite" in url:
            from sqlalchemy.pool import NullPool
            engine_kwargs["poolclass"] = NullPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        elif "postgresql" in url or "postgres" in url:
            from sqlalchemy.pool import AsyncAdaptedQueuePool
            engine_kwargs["poolclass"] = AsyncAdaptedQueuePool
            engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
            engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
            engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT
            engine_kwargs["pool_recycle"] = settings.DB_POOL_RECYCLE
            engine_kwargs["pool_pre_ping"] = True
        else:
            from sqlalchemy.pool import NullPool
            engine_kwargs["poolclass"] = NullPool
        _engine = create_async_engine(url, **engine_kwargs)
    return _engine


def get_session_factory(db_url: str | None = None):
    global _session_factory
    if _session_factory is None or db_url is not None:
        engine = get_engine(db_url)
        _session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields an AsyncSession."""
    url = settings.DATABASE_URL
    if "sqlite" in url and url not in _initialized_urls:
        async with _init_lock:
            if url not in _initialized_urls:
                await init_db(url)
                _initialized_urls.add(url)
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db(db_url: str | None = None):
    """Create all tables for SQLite/testing workflows."""
    url = db_url or settings.DATABASE_URL
    engine = get_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _initialized_urls.add(url)


async def drop_db(db_url: str | None = None):
    """Drop all tables. For testing only."""
    engine = get_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def reset_engine():
    """Reset the global engine (for testing)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
    _initialized_urls.clear()
