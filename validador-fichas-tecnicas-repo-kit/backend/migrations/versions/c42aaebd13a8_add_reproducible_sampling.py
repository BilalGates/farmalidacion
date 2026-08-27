'''Add reproducible CIMA sampling runs and items.'''

import sqlalchemy as sa
from alembic import op

revision = 'c42aaebd13a8'
down_revision = '9b01a03d5247'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sampling_run',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('mode', sa.String(length=20), nullable=False),
        sa.Column('seed', sa.Integer(), nullable=False),
        sa.Column('requested_size', sa.Integer(), nullable=False),
        sa.Column('eligible_count', sa.Integer(), nullable=False),
        sa.Column('excluded_count', sa.Integer(), nullable=False),
        sa.Column('source_snapshot_hash', sa.String(length=64), nullable=False),
        sa.Column('algorithm_version', sa.String(length=40), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'sampling_item',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('sampling_run_id', sa.String(length=64), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('nregistro', sa.Text(), nullable=False),
        sa.Column('atc_stratum', sa.String(length=20), nullable=True),
        sa.Column('source_response_hash', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['sampling_run_id'], ['sampling_run.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'sampling_run_id', 'nregistro', name='uq_sampling_item_nregistro'
        ),
        sa.UniqueConstraint('sampling_run_id', 'ordinal', name='uq_sampling_item_ordinal'),
    )


def downgrade() -> None:
    op.drop_table('sampling_item')
    op.drop_table('sampling_run')
