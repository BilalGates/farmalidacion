"""Add Phase 6 export, second review, reconciliation and audit (DEV-604..609).

Migración aditiva. No modifica ninguna tabla existente: sólo crea las cinco
tablas que la Fase 6 necesita, de modo que una base ya cargada siga leyéndose
exactamente igual y el downgrade no pueda tocar dato importado.
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("actor_assurance", sa.String(length=20), nullable=False),
        sa.Column("before_state", sa.Text(), nullable=True),
        sa.Column("after_state", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_event_entity", "audit_event", ["entity_type", "entity_id"])
    op.create_index("ix_audit_event_recorded", "audit_event", ["recorded_at"])

    op.create_table(
        "second_review_assignment",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("field_value_id", sa.String(length=36), nullable=False),
        sa.Column("target_record_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("first_reviewer_id", sa.String(length=80), nullable=False),
        sa.Column("first_decision_sequence", sa.Integer(), nullable=False),
        sa.Column("second_reviewer_id", sa.String(length=80), nullable=True),
        sa.Column("second_decision_sequence", sa.Integer(), nullable=True),
        sa.Column(
            "revealed", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["field_value_id"], ["field_value.id"]),
        sa.ForeignKeyConstraint(["target_record_id"], ["target_record.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_value_id", name="uq_second_review_field"),
    )
    op.create_index(
        "ix_second_review_assignment_field_value_id",
        "second_review_assignment",
        ["field_value_id"],
    )
    op.create_index(
        "ix_second_review_assignment_target_record_id",
        "second_review_assignment",
        ["target_record_id"],
    )
    op.create_index("ix_second_review_state", "second_review_assignment", ["state"])

    op.create_table(
        "reconciliation_record",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("field_value_id", sa.String(length=36), nullable=False),
        sa.Column("reconciler_id", sa.String(length=80), nullable=False),
        sa.Column("reconciler_assurance", sa.String(length=20), nullable=False),
        sa.Column("resulting_sequence", sa.Integer(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["second_review_assignment.id"]),
        sa.ForeignKeyConstraint(["field_value_id"], ["field_value.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", name="uq_reconciliation_assignment"),
    )
    op.create_index(
        "ix_reconciliation_record_assignment_id",
        "reconciliation_record",
        ["assignment_id"],
    )
    op.create_index(
        "ix_reconciliation_record_field_value_id",
        "reconciliation_record",
        ["field_value_id"],
    )

    op.create_table(
        "export_run",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_name", sa.String(length=120), nullable=False),
        sa.Column("profile_version", sa.String(length=40), nullable=False),
        sa.Column("export_format", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("excluded_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("profile_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_run_created", "export_run", ["created_at"])

    op.create_table(
        "export_exclusion",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("export_run_id", sa.String(length=36), nullable=False),
        sa.Column("target_record_id", sa.String(length=36), nullable=False),
        sa.Column("field_name", sa.String(length=160), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("rule", sa.String(length=120), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("observed_state", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["export_run_id"], ["export_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_export_exclusion_export_run_id", "export_exclusion", ["export_run_id"]
    )
    op.create_index("ix_export_exclusion_run", "export_exclusion", ["export_run_id"])


def downgrade() -> None:
    op.drop_index("ix_export_exclusion_run", table_name="export_exclusion")
    op.drop_index("ix_export_exclusion_export_run_id", table_name="export_exclusion")
    op.drop_table("export_exclusion")
    op.drop_index("ix_export_run_created", table_name="export_run")
    op.drop_table("export_run")
    op.drop_index(
        "ix_reconciliation_record_field_value_id", table_name="reconciliation_record"
    )
    op.drop_index(
        "ix_reconciliation_record_assignment_id", table_name="reconciliation_record"
    )
    op.drop_table("reconciliation_record")
    op.drop_index("ix_second_review_state", table_name="second_review_assignment")
    op.drop_index(
        "ix_second_review_assignment_target_record_id",
        table_name="second_review_assignment",
    )
    op.drop_index(
        "ix_second_review_assignment_field_value_id",
        table_name="second_review_assignment",
    )
    op.drop_table("second_review_assignment")
    op.drop_index("ix_audit_event_recorded", table_name="audit_event")
    op.drop_index("ix_audit_event_entity", table_name="audit_event")
    op.drop_table("audit_event")
