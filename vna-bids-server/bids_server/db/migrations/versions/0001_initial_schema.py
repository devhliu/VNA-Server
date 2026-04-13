"""Initial schema - all BIDS server tables."""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subjects",
        sa.Column("subject_id", sa.String(64), primary_key=True),
        sa.Column("patient_ref", sa.String(128), nullable=True),
        sa.Column("hospital_ids", sa.JSON, default=dict),
        sa.Column("metadata", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(128), primary_key=True),
        sa.Column("subject_id", sa.String(64), sa.ForeignKey("subjects.subject_id"), nullable=False),
        sa.Column("session_label", sa.String(64)),
        sa.Column("scan_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_sessions_subject", "sessions", ["subject_id"])
    op.create_index("idx_sessions_composite", "sessions", ["subject_id", "session_label"])

    op.create_table(
        "resources",
        sa.Column("resource_id", sa.String(64), primary_key=True),
        sa.Column("subject_id", sa.String(64), sa.ForeignKey("subjects.subject_id", deferrable=True), nullable=True),
        sa.Column("session_id", sa.String(128), sa.ForeignKey("sessions.session_id", deferrable=True), nullable=True),
        sa.Column("modality", sa.String(32), nullable=False),
        sa.Column("bids_path", sa.Text, nullable=False, unique=True),
        sa.Column("file_name", sa.String(256), nullable=False),
        sa.Column("file_type", sa.String(32)),
        sa.Column("file_size", sa.BigInteger, default=0),
        sa.Column("content_hash", sa.String(128)),
        sa.Column("source", sa.String(32), default="user_upload"),
        sa.Column("dicom_ref", sa.String(256), nullable=True),
        sa.Column("metadata", sa.JSON, default=dict),
        sa.Column("search_vector", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_resources_subject", "resources", ["subject_id"])
    op.create_index("idx_resources_session", "resources", ["session_id"])
    op.create_index("idx_resources_modality", "resources", ["modality"])
    op.create_index("idx_resources_hash", "resources", ["content_hash"])
    op.create_index("idx_resources_composite", "resources", ["subject_id", "session_id", "modality"])

    op.create_table(
        "labels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("resource_id", sa.String(64), sa.ForeignKey("resources.resource_id", ondelete="CASCADE"), nullable=True),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("target_path", sa.Text),
        sa.Column("tag_key", sa.String(128), nullable=False),
        sa.Column("tag_value", sa.Text),
        sa.Column("tagged_by", sa.String(128)),
        sa.Column("tagged_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_labels_resource", "labels", ["resource_id"])
    op.create_index("idx_labels_key", "labels", ["tag_key"])
    op.create_index("idx_labels_value", "labels", ["tag_value"])
    op.create_index("idx_labels_target", "labels", ["target_path"])

    op.create_table(
        "annotations",
        sa.Column("annotation_id", sa.String(64), primary_key=True),
        sa.Column("resource_id", sa.String(64), sa.ForeignKey("resources.resource_id", ondelete="CASCADE"), nullable=False),
        sa.Column("ann_type", sa.String(32), nullable=False),
        sa.Column("label", sa.String(128)),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("created_by", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_annotations_resource", "annotations", ["resource_id"])
    op.create_index("idx_annotations_type", "annotations", ["ann_type"])

    op.create_table(
        "processing_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("resource_id", sa.String(64), sa.ForeignKey("resources.resource_id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline", sa.String(128)),
        sa.Column("input_resources", sa.JSON, default=list),
        sa.Column("params", sa.JSON, default=dict),
        sa.Column("executed_by", sa.String(128)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_processing_resource", "processing_log", ["resource_id"])

    op.create_table(
        "relationships",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("resource_id", sa.String(64), sa.ForeignKey("resources.resource_id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("parent_refs", sa.JSON, default=list),
        sa.Column("children_refs", sa.JSON, default=list),
        sa.Column("dicom_ref", sa.String(256), nullable=True),
        sa.Column("same_subject", sa.JSON, default=list),
    )

    op.create_table(
        "tasks",
        sa.Column("task_id", sa.String(64), primary_key=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_ids", sa.JSON, default=list),
        sa.Column("params", sa.JSON, default=dict),
        sa.Column("status", sa.String(16), default="queued"),
        sa.Column("progress", sa.Float, default=0),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("callback_url", sa.Text, nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, default=0),
        sa.Column("max_attempts", sa.Integer, nullable=False, default=4),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_tasks_status", "tasks", ["status"])
    op.create_index("idx_tasks_due", "tasks", ["status", "next_attempt_at"])

    op.create_table(
        "webhooks",
        sa.Column("webhook_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128)),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("events", sa.JSON, nullable=False),
        sa.Column("secret", sa.String(256), nullable=True),
        sa.Column("filters", sa.JSON, default=dict),
        sa.Column("active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("delivery_id", sa.String(64), primary_key=True),
        sa.Column("webhook_id", sa.String(64), nullable=True),
        sa.Column("target_url", sa.Text, nullable=False),
        sa.Column("secret", sa.String(256), nullable=True),
        sa.Column("event", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, default="queued"),
        sa.Column("attempt_count", sa.Integer, nullable=False, default=0),
        sa.Column("max_attempts", sa.Integer, nullable=False, default=6),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("idx_webhook_deliveries_due", "webhook_deliveries", ["status", "next_attempt_at"])

    op.create_table(
        "bids_datasets",
        sa.Column("dataset_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("dataset_path", sa.Text, nullable=False),
        sa.Column("version", sa.String(32), default="1.0.0"),
        sa.Column("is_valid", sa.Boolean, default=False),
        sa.Column("validation_report", sa.JSON, nullable=True),
        sa.Column("subject_count", sa.Integer, default=0),
        sa.Column("session_count", sa.Integer, default=0),
        sa.Column("total_size", sa.BigInteger, default=0),
        sa.Column("created_by", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "bids_sessions",
        sa.Column("session_id", sa.String(128), primary_key=True),
        sa.Column("dataset_id", sa.String(64), sa.ForeignKey("bids_datasets.dataset_id"), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("session_label", sa.String(64), nullable=True),
        sa.Column("scan_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "conversion_jobs",
        sa.Column("job_id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.task_id"), nullable=True),
        sa.Column("input_path", sa.Text, nullable=True),
        sa.Column("output_path", sa.Text, nullable=True),
        sa.Column("config", sa.JSON, default=dict),
        sa.Column("status", sa.String(16), default="pending"),
        sa.Column("progress", sa.Float, default=0),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_conversion_jobs_status", "conversion_jobs", ["status"])

    op.create_table(
        "modalities",
        sa.Column("modality_id", sa.String(64), primary_key=True),
        sa.Column("directory", sa.String(64), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("extensions", sa.JSON, nullable=False),
        sa.Column("required_files", sa.JSON, default=lambda: ["json"]),
        sa.Column("category", sa.String(32), default="other"),
        sa.Column("is_system", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("modalities")
    op.drop_index("idx_conversion_jobs_status", table_name="conversion_jobs")
    op.drop_table("conversion_jobs")
    op.drop_table("bids_sessions")
    op.drop_table("bids_datasets")
    op.drop_index("idx_webhook_deliveries_due", table_name="webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")
    op.drop_index("idx_tasks_due", table_name="tasks")
    op.drop_index("idx_tasks_status", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("relationships")
    op.drop_index("idx_processing_resource", table_name="processing_log")
    op.drop_table("processing_log")
    op.drop_index("idx_annotations_type", table_name="annotations")
    op.drop_index("idx_annotations_resource", table_name="annotations")
    op.drop_table("annotations")
    op.drop_index("idx_labels_target", table_name="labels")
    op.drop_index("idx_labels_value", table_name="labels")
    op.drop_index("idx_labels_key", table_name="labels")
    op.drop_index("idx_labels_resource", table_name="labels")
    op.drop_table("labels")
    op.drop_index("idx_resources_composite", table_name="resources")
    op.drop_index("idx_resources_hash", table_name="resources")
    op.drop_index("idx_resources_modality", table_name="resources")
    op.drop_index("idx_resources_session", table_name="resources")
    op.drop_index("idx_resources_subject", table_name="resources")
    op.drop_table("resources")
    op.drop_index("idx_sessions_composite", table_name="sessions")
    op.drop_index("idx_sessions_subject", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("subjects")
