"""accounts and transfers: transfer pairs, credit cards, payment categories

Revision ID: 8d3a6b2c5e71
Revises: 7c2f1e9a4b10
Create Date: 2026-10-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d3a6b2c5e71'
down_revision: Union[str, Sequence[str], None] = '7c2f1e9a4b10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'transactions', sa.Column('transfer_pair_id', sa.String(length=36), nullable=True)
    )
    op.create_index(
        op.f('ix_transactions_transfer_pair_id'), 'transactions', ['transfer_pair_id']
    )
    op.add_column(
        'accounts',
        sa.Column('archived', sa.Boolean(), server_default='false', nullable=False),
    )
    op.add_column('accounts', sa.Column('payment_day', sa.Integer(), nullable=True))
    op.add_column(
        'categories', sa.Column('payment_account_id', sa.String(length=36), nullable=True)
    )
    op.create_foreign_key(
        'fk_categories_payment_account_id_accounts',
        'categories', 'accounts', ['payment_account_id'], ['id'],
    )
    op.create_unique_constraint(
        'uq_categories_payment_account_id', 'categories', ['payment_account_id']
    )
    op.add_column(
        'category_groups',
        sa.Column('system', sa.Boolean(), server_default='false', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('category_groups', 'system')
    op.drop_constraint('uq_categories_payment_account_id', 'categories', type_='unique')
    op.drop_constraint(
        'fk_categories_payment_account_id_accounts', 'categories', type_='foreignkey'
    )
    op.drop_column('categories', 'payment_account_id')
    op.drop_column('accounts', 'payment_day')
    op.drop_column('accounts', 'archived')
    op.drop_index(op.f('ix_transactions_transfer_pair_id'), table_name='transactions')
    op.drop_column('transactions', 'transfer_pair_id')
