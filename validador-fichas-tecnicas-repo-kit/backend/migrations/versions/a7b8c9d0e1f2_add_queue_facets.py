"""add explicit review queue facets

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""

from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("review_queue_entry") as batch:
        batch.add_column(
            sa.Column("review_set", sa.String(length=20), server_default="corpus", nullable=False)
        )
        batch.add_column(
            sa.Column("requires_second_review", sa.Boolean(), server_default="0", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("review_queue_entry") as batch:
        batch.drop_column("requires_second_review")
        batch.drop_column("review_set")
