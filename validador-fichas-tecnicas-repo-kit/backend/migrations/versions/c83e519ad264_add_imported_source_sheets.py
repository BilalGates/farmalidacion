"""Add per-sheet import evidence."""

import sqlalchemy as sa
from alembic import op

revision = "c83e519ad264"
down_revision = "b72f41c9e805"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "imported_source_sheet",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("import_batch_id", sa.String(length=64), nullable=False),
        sa.Column("sheet_name", sa.Text(), nullable=False),
        sa.Column("sheet_ordinal", sa.Integer(), nullable=False),
        sa.Column("header_row_number", sa.Integer(), nullable=False),
        sa.Column("header_payload", sa.Text(), nullable=False),
        sa.Column("data_row_count", sa.Integer(), nullable=False),
        sa.Column("material_value_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "import_batch_id", "sheet_ordinal", name="uq_imported_source_sheet_ordinal"
        ),
    )


def downgrade() -> None:
    op.drop_table("imported_source_sheet")
