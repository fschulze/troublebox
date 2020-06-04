"""Add projects table.

Revision ID: 604d83a8c90e
Revises: ccb528164bd7
Create Date: 2020-06-04 11:11:57.557395

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '604d83a8c90e'
down_revision = 'ccb528164bd7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.Unicode(), nullable=True),
        sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_index(op.f('ix_events_project_id'), table_name='events')
    op.drop_table('projects')
