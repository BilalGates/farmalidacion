"""Add indexes for the record traversal paths.

Ninguna clave foránea estaba indexada. Mientras los datos eran el conjunto DEMO
(cinco registros) no se notaba; con los maestros reales importados —7.189
registros y 35.945 valores— cada lectura recorría la tabla entera: SQLite
resolvía `SELECT ... WHERE field_value_id = ?` con un SCAN de 35.945 filas, y
una sola consulta costaba ~163 ms.

Los índices siguen exactamente los recorridos que hace el listado: valores por
ocurrencia, ocurrencias por registro, procedencia por valor, y la decisión
vigente de un campo (que se lee por `field_value_id` ordenando por `sequence`
descendente, de ahí el índice compuesto).
"""

from alembic import op

revision = "f19a4c7b6d82"
down_revision = "d51f7a2c9e04"
branch_labels = None
depends_on = None

# (nombre, tabla, columnas)
INDEXES: tuple[tuple[str, str, list[str]], ...] = (
    ("ix_block_instance_target_record", "block_instance", ["target_record_id"]),
    ("ix_field_value_block_instance", "field_value", ["block_instance_id"]),
    ("ix_field_value_field_name", "field_value", ["field_name"]),
    ("ix_value_provenance_field_value", "value_provenance", ["field_value_id"]),
    ("ix_value_provenance_source_fragment", "value_provenance", ["source_fragment_id"]),
    ("ix_external_identifier_target_record", "external_identifier", ["target_record_id"]),
    ("ix_document_record_link_target_record", "document_record_link", ["target_record_id"]),
    ("ix_target_record_link_source_record", "target_record_link", ["source_record_id"]),
    ("ix_target_record_link_target_record", "target_record_link", ["target_record_id"]),
    ("ix_source_fragment_document_version", "source_fragment", ["document_version_id"]),
    # La decisión vigente es la de mayor `sequence` para un campo: el índice
    # compuesto la resuelve sin ordenar ni recorrer el historial completo.
    (
        "ix_validation_decision_field_value_sequence",
        "validation_decision_record",
        ["field_value_id", "sequence"],
    ),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
