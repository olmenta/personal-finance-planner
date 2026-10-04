"""category kind and payment schedules

Revision ID: 7c2f1e9a4b10
Revises: 43666f3761ac
Create Date: 2026-10-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7c2f1e9a4b10'
down_revision: Union[str, Sequence[str], None] = '43666f3761ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'categories',
        sa.Column('kind', sa.String(length=12), server_default='flexible', nullable=False),
    )
    op.create_table(
        'payment_schedules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('category_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('pattern', sa.String(length=12), nullable=False),
        sa.Column('months', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('month', sa.Integer(), nullable=True),
        sa.Column('every_n', sa.Integer(), nullable=True),
        sa.Column('start_month', sa.String(length=7), nullable=True),
        sa.Column('count', sa.Integer(), nullable=True),
        sa.Column('once_month', sa.String(length=7), nullable=True),
        sa.Column('day', sa.Integer(), nullable=True),
        sa.Column('estimated', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_payment_schedules_user_category', 'payment_schedules', ['user_id', 'category_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_payment_schedules_user_category', table_name='payment_schedules')
    op.drop_table('payment_schedules')
    op.drop_column('categories', 'kind')
