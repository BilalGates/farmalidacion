'''Add immutable byte-preserving source document artifacts.'''

import sqlalchemy as sa
from alembic import op

revision = 'e3c83b4ed201'
down_revision = 'c42aaebd13a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'source_document_artifact',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('document_version_id', sa.String(length=36), nullable=False),
        sa.Column('artifact_role', sa.String(length=40), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('locator', sa.Text(), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('media_type', sa.Text(), nullable=True),
        sa.Column('response_headers', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('body', sa.LargeBinary(), nullable=False),
        sa.Column('fetched_at', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['document_version_id'], ['source_document_version.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'document_version_id',
            'artifact_role',
            'ordinal',
            name='uq_source_document_artifact_occurrence',
        ),
    )


def downgrade() -> None:
    op.drop_table('source_document_artifact')
