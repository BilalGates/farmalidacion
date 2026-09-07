'''Add the covering index used by server-side record search.

The record list searches only display-name and master-identifier field values.
With 2.17 million values, the previous single-column index located the 221,226
candidate rows but SQLite still had to visit the table once per candidate to
read the literal and block id. This index covers that exact traversal; it does
not change search semantics or introduce a speculative index.
'''

from alembic import op

revision = '4d7a6b2c1e90'
down_revision = 'f19a4c7b6d82'
branch_labels = None
depends_on = None

INDEX_NAME = 'ix_field_value_record_search'


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        'field_value',
        ['field_name', 'literal_value', 'block_instance_id'],
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name='field_value')
