"""Prevent two editable fields from claiming one source cell in a block."""

from alembic import op

revision = "f9a0b1c2d3e4"
down_revision = "e8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("field_value") as batch:
        batch.create_unique_constraint(
            "uq_field_value_block_source_column", ["block_instance_id", "source_column_index"]
        )


def downgrade() -> None:
    with op.batch_alter_table("field_value") as batch:
        batch.drop_constraint("uq_field_value_block_source_column", type_="unique")
