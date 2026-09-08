"""Add review session timing so the pilot can measure time saved.

Raw focus intervals are stored alongside the aggregates on purpose: the
inactivity discount is a rule that may be revisited, and an aggregate cannot be
undone. `is_synthetic` marks engineering or pilot sessions so they can never be
summed into a figure presented as real pharmacist time saved.
"""

import sqlalchemy as sa
from alembic import op

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'review_session',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('target_record_id', sa.String(length=36), sa.ForeignKey('target_record.id'),
                  nullable=False),
        sa.Column('reviewer_id', sa.String(length=80), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('counted_seconds', sa.Integer(), nullable=False),
        sa.Column('discarded_seconds', sa.Integer(), nullable=False),
        sa.Column('measured_field_count', sa.Integer(), nullable=False),
        sa.Column('capped_field_count', sa.Integer(), nullable=False),
        sa.Column('is_synthetic', sa.Boolean(), nullable=False),
    )
    op.create_index('ix_review_session_record', 'review_session', ['target_record_id'])
    op.create_index('ix_review_session_reviewer', 'review_session', ['reviewer_id'])
    op.create_table(
        'field_focus_interval',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('review_session_id', sa.String(length=36),
                  sa.ForeignKey('review_session.id'), nullable=False),
        sa.Column('field_name', sa.String(length=160), nullable=False),
        sa.Column('started_at', sa.Float(), nullable=False),
        sa.Column('ended_at', sa.Float(), nullable=False),
    )
    op.create_index('ix_field_focus_session', 'field_focus_interval', ['review_session_id'])


def downgrade() -> None:
    op.drop_index('ix_field_focus_session', table_name='field_focus_interval')
    op.drop_table('field_focus_interval')
    op.drop_index('ix_review_session_reviewer', table_name='review_session')
    op.drop_index('ix_review_session_record', table_name='review_session')
    op.drop_table('review_session')
