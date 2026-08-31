"""Add lossless catalog field definitions."""

import sqlalchemy as sa
from alembic import op

revision = "b72f41c9e805"
down_revision = "a4d2c8f71b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_field_definition",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("import_batch_id", sa.String(length=64), nullable=False),
        sa.Column("sheet_name", sa.Text(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("sequence_literal", sa.Text(), nullable=False),
        sa.Column("entity_literal", sa.Text(), nullable=False),
        sa.Column("block_literal", sa.Text(), nullable=False),
        sa.Column("field_name_literal", sa.Text(), nullable=False),
        sa.Column("declared_type_literal", sa.Text(), nullable=False),
        sa.Column("effective_type", sa.Text(), nullable=False),
        sa.Column("override_decision", sa.String(length=40), nullable=True),
        sa.Column("required_literal", sa.Text(), nullable=True),
        sa.Column("from_ft_literal", sa.Text(), nullable=True),
        sa.Column("ft_section_literal", sa.Text(), nullable=True),
        sa.Column("comment_literal", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "import_batch_id", "source_row_number", name="uq_catalog_field_source_row"
        ),
    )


def downgrade() -> None:
    op.drop_table("catalog_field_definition")
