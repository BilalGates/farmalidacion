"""Add recoverable daily CIMA maintenance runs (DEV-704)."""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_run",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("requested_date", sa.String(length=10), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requested_date", "attempt", name="uq_maintenance_run_attempt"),
    )
    op.create_index("ix_maintenance_run_requested_date", "maintenance_run", ["requested_date"])
    op.create_index("ix_maintenance_run_started", "maintenance_run", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_maintenance_run_started", table_name="maintenance_run")
    op.drop_index("ix_maintenance_run_requested_date", table_name="maintenance_run")
    op.drop_table("maintenance_run")
