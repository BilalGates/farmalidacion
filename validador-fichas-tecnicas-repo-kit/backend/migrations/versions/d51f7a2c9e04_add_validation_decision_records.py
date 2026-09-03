"""Add append-only validation decision records."""

import sqlalchemy as sa
from alembic import op

revision = "d51f7a2c9e04"
down_revision = "c83e519ad264"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_decision_record",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("field_value_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("final_value", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.String(length=80), nullable=False),
        sa.Column("reviewer_role", sa.String(length=40), nullable=False),
        sa.Column("reviewer_assurance", sa.String(length=20), nullable=False),
        sa.Column("seconds_spent", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["field_value_id"], ["field_value.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "field_value_id", "sequence", name="uq_validation_decision_sequence"
        ),
    )


def downgrade() -> None:
    op.drop_table("validation_decision_record")
