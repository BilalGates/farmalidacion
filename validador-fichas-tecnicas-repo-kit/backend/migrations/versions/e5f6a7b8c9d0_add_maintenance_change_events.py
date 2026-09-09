"""Add immutable CIMA maintenance events (DEV-703)."""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_change_event",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("nregistro", sa.String(length=80), nullable=False),
        sa.Column("occurred_at_epoch", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.Integer(), nullable=False),
        sa.Column("areas_json", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.Text(), nullable=False),
        sa.Column("old_version_id", sa.String(length=36), nullable=True),
        sa.Column("new_version_id", sa.String(length=36), nullable=True),
        sa.Column("diff_json", sa.Text(), nullable=True),
        sa.Column("affected_field_count", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["old_version_id"], ["source_document_version.id"]),
        sa.ForeignKeyConstraint(["new_version_id"], ["source_document_version.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_maintenance_change_event_nregistro",
        "maintenance_change_event",
        ["nregistro"],
    )
    op.create_index(
        "ix_maintenance_change_event_occurred",
        "maintenance_change_event",
        ["occurred_at_epoch"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_maintenance_change_event_occurred", table_name="maintenance_change_event"
    )
    op.drop_index(
        "ix_maintenance_change_event_nregistro", table_name="maintenance_change_event"
    )
    op.drop_table("maintenance_change_event")
