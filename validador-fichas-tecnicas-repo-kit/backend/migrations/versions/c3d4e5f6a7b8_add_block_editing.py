"""Add block editing persistence and audit (DEV-507).

El núcleo de decisión (`block_editing`) existía desde Fase 5 pero era puro: no
había dónde guardar ni la marca de «no aplicable» de una ocurrencia ni el
rastro de qué se creó, eliminó, reordenó o fusionó.

La migración es aditiva. No toca las tablas del corpus importado más allá de
añadir dos columnas con valor por defecto a `block_instance`, de modo que una
base ya cargada siga leyéndose igual: ninguna ocurrencia existente queda
marcada como no aplicable y ninguna fila se reescribe.
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `server_default` es imprescindible: sin él, las 113.640 ocurrencias ya
    # importadas quedarían con NULL en una columna no nula.
    op.add_column(
        "block_instance",
        sa.Column(
            "not_applicable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column("block_instance", sa.Column("edit_comment", sa.Text(), nullable=True))

    op.create_table(
        "block_edit_record",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("target_record_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.String(length=120), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("affected_ids", sa.Text(), nullable=False),
        # El estado previo se conserva para que fusionar o eliminar no destruya
        # el dato de origen: sin esto, la operación sería irreversible de hecho.
        sa.Column("before_state", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.String(length=80), nullable=False),
        sa.Column("reviewer_assurance", sa.String(length=20), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["target_record_id"], ["target_record.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("target_record_id", "sequence", name="uq_block_edit_sequence"),
    )
    op.create_index(
        "ix_block_edit_record_target_record_id", "block_edit_record", ["target_record_id"]
    )
    op.create_index(
        "ix_block_edit_record_sequence", "block_edit_record", ["target_record_id", "sequence"]
    )


def downgrade() -> None:
    op.drop_index("ix_block_edit_record_sequence", table_name="block_edit_record")
    op.drop_index("ix_block_edit_record_target_record_id", table_name="block_edit_record")
    op.drop_table("block_edit_record")
    # SQLite no soporta DROP COLUMN en versiones antiguas; Alembic usa el modo
    # de recreación de tabla, que preserva los datos existentes.
    with op.batch_alter_table("block_instance") as batch:
        batch.drop_column("edit_comment")
        batch.drop_column("not_applicable")
