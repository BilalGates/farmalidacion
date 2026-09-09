"""add reviewer directory with role and activation

Revision ID: d5e6f7a8b9c0
Revises: a7b8c9d0e1f2
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

#: Semilla mínima. Los revisores vivían en `APP_REVIEWERS`, así que una base ya
#: en uso tiene decisiones firmadas por ellos: sin estas filas el selector
#: aparecería vacío y esas firmas quedarían sin respaldo en la lista.
#: `farmaceutico` es el rol que la configuración asumía de facto.
SEED = (
    ("mtorres", "M. Torres", "farmaceutico"),
    ("jlopez", "J. Lopez", "farmaceutico"),
)


def upgrade() -> None:
    reviewer = op.create_table(
        "reviewer",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("identifier", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("identifier", name="uq_reviewer_identifier"),
    )
    op.create_index("ix_reviewer_active", "reviewer", ["active"])
    op.bulk_insert(
        reviewer,
        [
            {
                "id": str(uuid.uuid4()),
                "identifier": identifier,
                "display_name": display_name,
                "role": role,
                "active": True,
                "created_at": datetime.now(UTC),
            }
            for identifier, display_name, role in SEED
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_reviewer_active", table_name="reviewer")
    op.drop_table("reviewer")
