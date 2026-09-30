"""Link observed CIMA events to exact master CN matches."""

import sqlalchemy as sa
from alembic import op

revision = "f3e4d5c6b7a8"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_change_event_target",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("target_record_id", sa.String(length=36), nullable=False),
        sa.Column("national_code", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["maintenance_change_event.id"]),
        sa.ForeignKeyConstraint(["target_record_id"], ["target_record.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "target_record_id", name="uq_maintenance_event_target"),
    )
    op.create_index(
        "ix_maintenance_change_event_target_event_id",
        "maintenance_change_event_target",
        ["event_id"],
    )
    op.create_index(
        "ix_maintenance_event_target_record",
        "maintenance_change_event_target",
        ["target_record_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_maintenance_event_target_record",
        table_name="maintenance_change_event_target",
    )
    op.drop_index(
        "ix_maintenance_change_event_target_event_id",
        table_name="maintenance_change_event_target",
    )
    op.drop_table("maintenance_change_event_target")
