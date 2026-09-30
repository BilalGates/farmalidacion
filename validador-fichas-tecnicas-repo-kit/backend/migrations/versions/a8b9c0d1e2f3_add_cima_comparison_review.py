"""Persist CAT-007 decisions against immutable CIMA evidence."""

import sqlalchemy as sa
from alembic import op

revision = "a8b9c0d1e2f3"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_cima_review_decision",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("field_value_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("document_version_id", sa.String(length=36), nullable=False),
        sa.Column("catalog_field_definition_id", sa.String(length=64), nullable=False),
        sa.Column("section_locator", sa.Text(), nullable=False),
        sa.Column("section_content_hash", sa.String(length=64), nullable=False),
        sa.Column("comparison_status", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("corrected_value", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("actor_assurance", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["field_value_id"], ["field_value.id"]),
        sa.ForeignKeyConstraint(["document_version_id"], ["source_document_version.id"]),
        sa.ForeignKeyConstraint(["catalog_field_definition_id"], ["catalog_field_definition.id"]),
        sa.UniqueConstraint("field_value_id", "sequence", name="uq_cima_review_sequence"),
    )
    op.create_index(
        "ix_cima_review_field_sequence",
        "catalog_cima_review_decision",
        ["field_value_id", "sequence"],
    )
    op.create_index(
        "ix_catalog_cima_review_decision_field_value_id",
        "catalog_cima_review_decision",
        ["field_value_id"],
    )
    op.create_index(
        "ix_catalog_cima_review_decision_document_version_id",
        "catalog_cima_review_decision",
        ["document_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_catalog_cima_review_decision_document_version_id",
        table_name="catalog_cima_review_decision",
    )
    op.drop_index(
        "ix_catalog_cima_review_decision_field_value_id",
        table_name="catalog_cima_review_decision",
    )
    op.drop_index("ix_cima_review_field_sequence", table_name="catalog_cima_review_decision")
    op.drop_table("catalog_cima_review_decision")
