"""Phase 2 tables - projects, treatment_events, audit_log.

Revision ID: 0002_phase2_tables
Revises: 0001_initial_schema
Create Date: 2026-04-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_phase2_tables"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("project_id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("principal_investigator", sa.String(256), nullable=True),
        sa.Column("settings", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "project_members",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_ref", sa.String(32), sa.ForeignKey("patient_mapping.patient_ref", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.String(64), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "project_resources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", sa.String(32), sa.ForeignKey("resource_index.resource_id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_by", sa.String(128), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "treatment_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("patient_ref", sa.String(32), sa.ForeignKey("patient_mapping.patient_ref", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("outcome", sa.Text, nullable=True),
        sa.Column("facility", sa.String(256), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(32), nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("treatment_events")
    op.drop_table("project_resources")
    op.drop_table("project_members")
    op.drop_table("projects")
