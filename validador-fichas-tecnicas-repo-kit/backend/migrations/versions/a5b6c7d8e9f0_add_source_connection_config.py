"""Store non-secret SQL Server connection settings with immutable revisions."""

import sqlalchemy as sa
from alembic import op

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_connection_config",
        sa.Column("source_key", sa.String(length=40), primary_key=True),
        sa.Column("host", sa.Text(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database_name", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "source_connection_revision",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_key", sa.String(length=40), nullable=False),
        sa.Column("before_config", sa.Text(), nullable=True),
        sa.Column("after_config", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_source_connection_revision_source_key", "source_connection_revision", ["source_key"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_connection_revision_source_key", table_name="source_connection_revision"
    )
    op.drop_table("source_connection_revision")
    op.drop_table("source_connection_config")
