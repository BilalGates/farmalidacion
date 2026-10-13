"""Vínculos de cuentas verificadas, sin cambiar firmas ni revisores existentes."""

import sqlalchemy as sa
from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_identity_binding",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("reviewer_identifier", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "object_id", name="uq_auth_subject"),
        sa.UniqueConstraint("reviewer_identifier", name="uq_auth_reviewer"),
    )


def downgrade() -> None:
    op.drop_table("auth_identity_binding")
