"""Preserve source column identity for duplicate Excel headers."""

import json
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("field_value", sa.Column("source_column_index", sa.Integer(), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT fv.id, bi.id AS block_id, sf.literal_text "
            "FROM field_value AS fv "
            "JOIN block_instance AS bi ON bi.id = fv.block_instance_id "
            "JOIN value_provenance AS vp ON vp.field_value_id = fv.id "
            "JOIN source_fragment AS sf ON sf.id = vp.source_fragment_id"
        )
    ).all()
    for field_id, block_id, literal_text in rows:
        if not literal_text:
            continue
        try:
            cells = json.loads(literal_text)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(cells, list):
            continue
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            column = cell.get("column")
            if not isinstance(column, int) or column < 1:
                continue
            # Mirrors the stable field ID used by all three workbook importers.
            expected_id = str(uuid5(NAMESPACE_URL, "\\x1f".join((block_id, str(column), "field"))))
            if expected_id == field_id:
                connection.execute(
                    sa.text("UPDATE field_value SET source_column_index = :column WHERE id = :id"),
                    {"column": column, "id": field_id},
                )
                break


def downgrade() -> None:
    op.drop_column("field_value", "source_column_index")
