'''Add the review work queue used to assign records to reviewers.

Unlike validation_decision_record, this table is mutable state: it tracks who
holds a record right now, not what was decided. The `version` column carries
optimistic locking so two reviewers cannot silently overwrite each other; the
unique constraint on target_record_id keeps one queue entry per record.
'''

import sqlalchemy as sa
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = '4d7a6b2c1e90'
branch_labels = None
depends_on = None

TABLE = 'review_queue_entry'


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('target_record_id', sa.String(length=36), sa.ForeignKey('target_record.id'),
                  nullable=False),
        sa.Column('state', sa.String(length=40), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('assignee_id', sa.String(length=80), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('target_record_id', name='uq_review_queue_target_record'),
    )
    op.create_index('ix_review_queue_state_priority', TABLE, ['state', 'priority'])
    op.create_index('ix_review_queue_assignee', TABLE, ['assignee_id'])


def downgrade() -> None:
    op.drop_index('ix_review_queue_assignee', table_name=TABLE)
    op.drop_index('ix_review_queue_state_priority', table_name=TABLE)
    op.drop_table(TABLE)
