"""debts

Revision ID: d6e3f9a2b1c7
Revises: c5d2e8f1a9b4
Create Date: 2026-10-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6e3f9a2b1c7'
down_revision: Union[str, Sequence[str], None] = 'c5d2e8f1a9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'debts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('category_id', sa.String(length=36), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('rate_bp', sa.Integer(), nullable=True),
        sa.Column('rate_period', sa.String(length=8), nullable=True),
        sa.Column('minimum_cents', sa.Integer(), nullable=True),
        sa.Column('owed_cents', sa.Integer(), nullable=True),
        sa.Column('due_month', sa.String(length=7), nullable=True),
        sa.Column('payee_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['payee_id'], ['payees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category_id'),
    )
    op.create_index('ix_debts_user_id', 'debts', ['user_id'])
    op.create_table(
        'debt_settings',
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('extra_monthly_cents', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('debt_settings')
    op.drop_index('ix_debts_user_id', table_name='debts')
    op.drop_table('debts')
