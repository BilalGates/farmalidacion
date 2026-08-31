"""Add common import batch, diagnostic, and quarantine infrastructure."""

import sqlalchemy as sa
from alembic import op

revision = "a4d2c8f71b30"
down_revision = "e3c83b4ed201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_batch",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("source_locator", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("importer_name", sa.String(length=120), nullable=False),
        sa.Column("importer_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_document_version_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["source_document_version_id"], ["source_document_version.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "source_locator",
            "source_version",
            "content_hash",
            "importer_name",
            "importer_version",
            name="uq_import_batch_identity",
        ),
    )
    op.create_table(
        "import_diagnostic",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("import_batch_id", sa.String(length=64), nullable=False),
        sa.Column("diagnostic_key", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("source_locator", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details_literal", sa.Text(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_batch_id", "diagnostic_key", name="uq_import_diagnostic_key"),
    )
    op.create_table(
        "quarantined_source_row",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("import_batch_id", sa.String(length=64), nullable=False),
        sa.Column("quarantine_key", sa.String(length=64), nullable=False),
        sa.Column("source_locator", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "import_batch_id", "quarantine_key", name="uq_quarantined_source_row_key"
        ),
    )


def downgrade() -> None:
    op.drop_table("quarantined_source_row")
    op.drop_table("import_diagnostic")
    op.drop_table("import_batch")
