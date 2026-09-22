"""add typed and editable medication catalog

Revision ID: b8c9d0e1f2a3
Revises: d5e6f7a8b9c0
Create Date: 2026-09-22

Migración aditiva de CAT-003/CAT-004. No transforma `target_record`, no puebla
identidades y no modifica `real.db` por sí sola.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "medication_catalog_identity",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("identity_type", sa.String(length=40), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("target_record_id", sa.String(length=36), nullable=True),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.Column("source_literal", sa.Text(), nullable=True),
        sa.Column("source_fragment_id", sa.String(length=36), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["source_fragment_id"], ["source_fragment.id"]),
        sa.ForeignKeyConstraint(["target_record_id"], ["target_record.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "identity_type",
            "code",
            "source_version",
            name="uq_medication_catalog_source_identity",
        ),
    )
    op.create_index(
        "ix_medication_catalog_identity_type_name",
        "medication_catalog_identity",
        ["identity_type", "display_name"],
    )
    op.create_index(
        "ix_medication_catalog_identity_target_record_id",
        "medication_catalog_identity",
        ["target_record_id"],
    )

    op.create_table(
        "medication_catalog_relation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("relation_type", sa.String(length=60), nullable=False),
        sa.Column("source_identity_id", sa.String(length=36), nullable=False),
        sa.Column("target_identity_id", sa.String(length=36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=True),
        sa.Column("source_fragment_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_identity_id"], ["medication_catalog_identity.id"]
        ),
        sa.ForeignKeyConstraint(["source_fragment_id"], ["source_fragment.id"]),
        sa.ForeignKeyConstraint(
            ["target_identity_id"], ["medication_catalog_identity.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "relation_type",
            "source_identity_id",
            "target_identity_id",
            name="uq_medication_catalog_relation",
        ),
    )
    op.create_index(
        "ix_medication_catalog_relation_source",
        "medication_catalog_relation",
        ["source_identity_id", "relation_type"],
    )
    op.create_index(
        "ix_medication_catalog_relation_target",
        "medication_catalog_relation",
        ["target_identity_id", "relation_type"],
    )

    op.create_table(
        "medication_catalog_classification",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("presentation_identity_id", sa.String(length=36), nullable=False),
        sa.Column("classification_type", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=80), nullable=False),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.Column("source_fragment_id", sa.String(length=36), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(
            ["presentation_identity_id"], ["medication_catalog_identity.id"]
        ),
        sa.ForeignKeyConstraint(["source_fragment_id"], ["source_fragment.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "presentation_identity_id",
            "classification_type",
            "value",
            "source_version",
            name="uq_medication_catalog_classification",
        ),
    )
    op.create_index(
        "ix_medication_catalog_classification_presentation_identity_id",
        "medication_catalog_classification",
        ["presentation_identity_id"],
    )
    op.create_index(
        "ix_medication_catalog_classification_value",
        "medication_catalog_classification",
        ["classification_type", "value"],
    )

    op.create_table(
        "medication_catalog_revision",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("identity_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("before_state", sa.Text(), nullable=True),
        sa.Column("after_state", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("actor_assurance", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["medication_catalog_identity.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "identity_id", "sequence", name="uq_medication_catalog_revision"
        ),
    )
    op.create_index(
        "ix_medication_catalog_revision_identity",
        "medication_catalog_revision",
        ["identity_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_medication_catalog_revision_identity", table_name="medication_catalog_revision"
    )
    op.drop_table("medication_catalog_revision")
    op.drop_index(
        "ix_medication_catalog_classification_value",
        table_name="medication_catalog_classification",
    )
    op.drop_index(
        "ix_medication_catalog_classification_presentation_identity_id",
        table_name="medication_catalog_classification",
    )
    op.drop_table("medication_catalog_classification")
    op.drop_index(
        "ix_medication_catalog_relation_target", table_name="medication_catalog_relation"
    )
    op.drop_index(
        "ix_medication_catalog_relation_source", table_name="medication_catalog_relation"
    )
    op.drop_table("medication_catalog_relation")
    op.drop_index(
        "ix_medication_catalog_identity_target_record_id",
        table_name="medication_catalog_identity",
    )
    op.drop_index(
        "ix_medication_catalog_identity_type_name",
        table_name="medication_catalog_identity",
    )
    op.drop_table("medication_catalog_identity")
