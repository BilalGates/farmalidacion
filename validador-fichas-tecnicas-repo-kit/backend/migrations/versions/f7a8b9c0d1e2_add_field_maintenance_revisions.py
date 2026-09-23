"""Add an audited maintenance layer for imported source fields."""

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "field_maintenance_revision",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("field_value_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("actor_assurance", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["field_value_id"], ["field_value.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_value_id", "sequence", name="uq_field_maintenance_sequence"),
    )
    op.create_index(
        "ix_field_maintenance_field_sequence",
        "field_maintenance_revision",
        ["field_value_id", "sequence"],
    )
    op.create_index(
        "ix_field_maintenance_revision_field_value_id",
        "field_maintenance_revision",
        ["field_value_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_field_maintenance_revision_field_value_id",
        table_name="field_maintenance_revision",
    )
    op.drop_index(
        "ix_field_maintenance_field_sequence",
        table_name="field_maintenance_revision",
    )
    op.drop_table("field_maintenance_revision")
