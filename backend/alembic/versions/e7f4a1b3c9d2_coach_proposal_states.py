"""coach proposal states

Revision ID: e7f4a1b3c9d2
Revises: d6e3f9a2b1c7
Create Date: 2026-10-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f4a1b3c9d2'
down_revision: Union[str, Sequence[str], None] = 'd6e3f9a2b1c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'coach_proposal_states',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('fingerprint', sa.String(length=120), nullable=False),
        sa.Column('state', sa.String(length=12), nullable=False),
        sa.Column('until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'fingerprint', name='uq_coach_state_user_fp'),
    )
    op.create_index('ix_coach_proposal_states_user_id', 'coach_proposal_states', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_coach_proposal_states_user_id', table_name='coach_proposal_states')
    op.drop_table('coach_proposal_states')
