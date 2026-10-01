"""Add display name and reversible archival state to source documents."""

import sqlalchemy as sa
from alembic import op

revision = "f4a5b6c7d8e9"
down_revision = "f3e4d5c6b7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_document", sa.Column("display_name", sa.Text(), nullable=True))
    op.add_column(
        "source_document",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("import_batch", sa.Column("started_by", sa.String(length=80), nullable=True))
    op.add_column("import_batch", sa.Column("reason", sa.Text(), nullable=True))
    op.create_table(
        "source_management_revision",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("previous_display_name", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("was_active", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_document.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_management_revision_source_document_id",
        "source_management_revision",
        ["source_document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_management_revision_source_document_id",
        table_name="source_management_revision",
    )
    op.drop_table("source_management_revision")
    op.drop_column("import_batch", "reason")
    op.drop_column("import_batch", "started_by")
    op.drop_column("source_document", "is_active")
    op.drop_column("source_document", "display_name")
