"""Initial db.

Revision ID: ccb528164bd7
Revises:
Create Date: 2020-02-04 16:47:51.712048

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ccb528164bd7'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Unicode(), nullable=True),
        sa.Column('project', sa.Integer(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id'))
    op.create_index(op.f('ix_events_project'), 'events', ['project'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_events_project_id'), table_name='events')
    op.drop_table('events')
