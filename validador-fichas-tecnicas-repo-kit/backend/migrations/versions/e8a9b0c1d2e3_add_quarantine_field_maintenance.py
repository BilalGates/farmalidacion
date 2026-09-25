"""Add append-only maintenance for source cells in quarantined rows."""

import sqlalchemy as sa
from alembic import op

revision = "e8a9b0c1d2e3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quarantined_field_maintenance_revision",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("quarantined_row_id", sa.String(length=64), nullable=False),
        sa.Column("source_column_index", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("actor_assurance", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["quarantined_row_id"], ["quarantined_source_row.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "quarantined_row_id",
            "source_column_index",
            "sequence",
            name="uq_quarantined_field_maintenance_sequence",
        ),
    )
    op.create_index(
        "ix_quarantined_field_maintenance_cell_sequence",
        "quarantined_field_maintenance_revision",
        ["quarantined_row_id", "source_column_index", "sequence"],
    )
    op.create_index(
        "ix_quarantined_field_maintenance_revision_quarantined_row_id",
        "quarantined_field_maintenance_revision",
        ["quarantined_row_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_quarantined_field_maintenance_revision_quarantined_row_id",
        table_name="quarantined_field_maintenance_revision",
    )
    op.drop_index(
        "ix_quarantined_field_maintenance_cell_sequence",
        table_name="quarantined_field_maintenance_revision",
    )
    op.drop_table("quarantined_field_maintenance_revision")
