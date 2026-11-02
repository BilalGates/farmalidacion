"""Acciones derivadas de novedades CIMA y sus decisiones append-only (ADR-0019)."""

import sqlalchemy as sa
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_action",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "event_id", sa.String(64),
            sa.ForeignKey("maintenance_change_event.id"), nullable=False,
        ),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("area", sa.String(40), nullable=False),
        sa.Column("data_origin", sa.String(10), nullable=False),
        sa.Column("target_record_id", sa.String(36), sa.ForeignKey("target_record.id")),
        sa.Column(
            "identity_id", sa.String(36), sa.ForeignKey("medication_catalog_identity.id")
        ),
        sa.Column("national_code", sa.Text()),
        sa.Column("master_workbook", sa.String(40)),
        sa.Column("master_sheet", sa.String(80)),
        sa.Column("master_field_name", sa.String(80)),
        sa.Column("master_field_value_id", sa.String(36), sa.ForeignKey("field_value.id")),
        sa.Column("master_value_literal", sa.Text()),
        sa.Column(
            "cima_version_id", sa.String(36), sa.ForeignKey("source_document_version.id")
        ),
        sa.Column("cima_pointer", sa.Text()),
        sa.Column("cima_value_literal", sa.Text()),
        sa.Column("proposed_value", sa.Text()),
        sa.Column("rule_id", sa.String(80)),
        sa.Column("proposal_json", sa.Text()),
        sa.Column("diagnostic_code", sa.String(60)),
        sa.Column("derivation_version", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_maintenance_action_event_id", "maintenance_action", ["event_id"])
    op.create_index(
        "ix_maintenance_action_target_record_id", "maintenance_action", ["target_record_id"]
    )
    op.create_index("ix_maintenance_action_identity_id", "maintenance_action", ["identity_id"])
    op.create_index(
        "ix_maintenance_action_origin_kind", "maintenance_action", ["data_origin", "kind"]
    )
    op.create_table(
        "maintenance_action_decision",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "action_id", sa.String(36), sa.ForeignKey("maintenance_action.id"), nullable=False
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "applied_revision_id", sa.String(36),
            sa.ForeignKey("medication_catalog_revision.id"),
        ),
        sa.Column(
            "applied_field_revision_id", sa.String(36),
            sa.ForeignKey("field_maintenance_revision.id"),
        ),
        sa.Column("actor_id", sa.String(80), nullable=False),
        sa.Column("actor_assurance", sa.String(20), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "action_id", "sequence", name="uq_maintenance_action_decision_sequence"
        ),
    )
    op.create_index(
        "ix_maintenance_action_decision_action_id", "maintenance_action_decision", ["action_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_maintenance_action_decision_action_id", table_name="maintenance_action_decision"
    )
    op.drop_table("maintenance_action_decision")
    op.drop_index("ix_maintenance_action_origin_kind", table_name="maintenance_action")
    op.drop_index("ix_maintenance_action_identity_id", table_name="maintenance_action")
    op.drop_index("ix_maintenance_action_target_record_id", table_name="maintenance_action")
    op.drop_index("ix_maintenance_action_event_id", table_name="maintenance_action")
    op.drop_table("maintenance_action")
