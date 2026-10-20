"""Decisiones de enriquecimiento Nomenclátor ligadas a instantánea inmutable."""

import sqlalchemy as sa
from alembic import op

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nomenclator_review_decision",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_subject_id", sa.String(200), nullable=False),
        sa.Column(
            "identity_id", sa.String(36),
            sa.ForeignKey("medication_catalog_identity.id"), nullable=False,
        ),
        sa.Column("field_name", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("source_cn", sa.String(7), nullable=False),
        sa.Column("source_value", sa.Text(), nullable=False),
        sa.Column("compared_value", sa.Text(), nullable=True),
        sa.Column("comparison_status", sa.String(40), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(80), nullable=False),
        sa.Column("actor_assurance", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_subject_id", "identity_id", "field_name", "sequence",
            name="uq_nomenclator_decision_sequence",
        ),
    )
    op.create_index(
        "ix_nomenclator_decision_identity_field",
        "nomenclator_review_decision", ["identity_id", "field_name"],
    )
    op.create_table(
        "nomenclator_user_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_subject_id", sa.String(200), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("snapshot_path", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("latest_source_date", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_nomenclator_user_snapshot_owner_subject_id",
        "nomenclator_user_snapshot", ["owner_subject_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nomenclator_user_snapshot_owner_subject_id",
        table_name="nomenclator_user_snapshot",
    )
    op.drop_table("nomenclator_user_snapshot")
    op.drop_index(
        "ix_nomenclator_decision_identity_field", table_name="nomenclator_review_decision",
    )
    op.drop_table("nomenclator_review_decision")
