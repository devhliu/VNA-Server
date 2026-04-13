"""Initial schema - all VNA Main Server tables.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-04-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_mapping",
        sa.Column("patient_ref", sa.String(32), primary_key=True),
        sa.Column("hospital_id", sa.String(256), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("external_system", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "resource_index",
        sa.Column("resource_id", sa.String(32), primary_key=True),
        sa.Column("patient_ref", sa.String(32), sa.ForeignKey("patient_mapping.patient_ref", ondelete="SET NULL"), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="dicom_only"),
        sa.Column("dicom_study_uid", sa.String(128), nullable=True),
        sa.Column("dicom_series_uid", sa.String(128), nullable=True),
        sa.Column("dicom_sop_uid", sa.String(128), nullable=True),
        sa.Column("bids_subject_id", sa.String(128), nullable=True),
        sa.Column("bids_session_id", sa.String(128), nullable=True),
        sa.Column("bids_path", sa.Text, nullable=True),
        sa.Column("data_type", sa.String(64), nullable=False, server_default="dicom"),
        sa.Column("file_name", sa.String(512), nullable=True),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Indexes for resource_index
    op.create_index("ix_resource_index_dicom_study_uid", "resource_index", ["dicom_study_uid"])
    op.create_index("ix_resource_index_bids_path", "resource_index", ["bids_path"])

    op.create_table(
        "labels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("resource_id", sa.String(32), sa.ForeignKey("resource_index.resource_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_key", sa.String(256), nullable=False),
        sa.Column("tag_value", sa.String(1024), nullable=False),
        sa.Column("tag_type", sa.String(32), nullable=False, server_default="custom"),
        sa.Column("tagged_by", sa.String(128), nullable=True),
        sa.Column("tagged_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "label_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("resource_id", sa.String(32), sa.ForeignKey("resource_index.resource_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_key", sa.String(256), nullable=False),
        sa.Column("tag_value", sa.String(1024), nullable=False),
        sa.Column("tag_type", sa.String(32), nullable=False, server_default="custom"),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("tagged_by", sa.String(128), nullable=True),
        sa.Column("tagged_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "sync_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_db", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("processed", sa.Boolean, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Indexes for sync_events
    op.create_index("ix_sync_events_processed", "sync_events", ["processed"])
    op.create_index("ix_sync_events_source_db", "sync_events", ["source_db"])
    op.create_index(
        "ix_sync_events_source_db_processed_created_at",
        "sync_events",
        ["source_db", "processed", "created_at"],
    )

    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("events", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("secret", sa.String(64), nullable=False),
        sa.Column("description", sa.String(256), nullable=True),
        sa.Column("enabled", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "webhook_delivery_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subscription_id", sa.Integer, sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("delivery_id", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("success", sa.Boolean, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("attempt_count", sa.Integer, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "resource_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("resource_id", sa.String(32), sa.ForeignKey("resource_index.resource_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("snapshot", sa.JSON, nullable=False),
        sa.Column("change_type", sa.String(16), nullable=False),
        sa.Column("change_description", sa.String(512), nullable=True),
        sa.Column("changed_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "data_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("snapshot_type", sa.String(32), server_default="manual"),
        sa.Column("resource_count", sa.Integer, server_default="0"),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "routing_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("rule_type", sa.String(32), server_default="data_type"),
        sa.Column("conditions", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("target", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer, server_default="100"),
        sa.Column("enabled", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("ix_sync_events_source_db_processed_created_at", table_name="sync_events")
    op.drop_index("ix_sync_events_source_db", table_name="sync_events")
    op.drop_index("ix_sync_events_processed", table_name="sync_events")
    op.drop_index("ix_resource_index_bids_path", table_name="resource_index")
    op.drop_index("ix_resource_index_dicom_study_uid", table_name="resource_index")

    # Drop tables
    op.drop_table("routing_rules")
    op.drop_table("data_snapshots")
    op.drop_table("resource_versions")
    op.drop_table("webhook_delivery_logs")
    op.drop_table("webhook_subscriptions")
    op.drop_table("sync_events")
    op.drop_table("label_history")
    op.drop_table("labels")
    op.drop_table("resource_index")
    op.drop_table("patient_mapping")
