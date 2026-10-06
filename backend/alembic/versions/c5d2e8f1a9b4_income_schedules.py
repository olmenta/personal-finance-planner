"""income schedules

Revision ID: c5d2e8f1a9b4
Revises: b4e1c9d2a7f3
Create Date: 2026-10-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c5d2e8f1a9b4'
down_revision: Union[str, Sequence[str], None] = 'b4e1c9d2a7f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The single expected figure in preferences becomes one monthly schedule
# (income-schedules design D6). Idempotent: users who already have income
# schedules are skipped. The preference keys stay as interview memory.
MIGRATE_EXPECTED_INCOME = sa.text(
    """
    INSERT INTO income_schedules
        (id, user_id, name, amount_cents, pattern, day, estimated, created_at)
    SELECT
        gen_random_uuid()::text,
        p.user_id,
        'Monthly income',
        (p.preferences -> 'income' ->> 'expected_monthly_cents')::bigint,
        'monthly',
        CASE
            WHEN jsonb_typeof(p.preferences -> 'income' -> 'income_day') = 'number'
             AND (p.preferences -> 'income' ->> 'income_day') ~ '^[0-9]+$'
             AND (p.preferences -> 'income' ->> 'income_day')::int BETWEEN 1 AND 31
            THEN (p.preferences -> 'income' ->> 'income_day')::int
        END,
        false,
        now()
    FROM user_preferences p
    WHERE jsonb_typeof(p.preferences -> 'income' -> 'expected_monthly_cents') = 'number'
      AND (p.preferences -> 'income' ->> 'expected_monthly_cents') ~ '^[0-9]+$'
      AND (p.preferences -> 'income' ->> 'expected_monthly_cents')::bigint BETWEEN 1 AND 2147483647
      AND NOT EXISTS (SELECT 1 FROM income_schedules s WHERE s.user_id = p.user_id)
    """
)


def migrate_expected_income(bind) -> None:
    bind.execute(MIGRATE_EXPECTED_INCOME)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'income_schedules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('payee_id', sa.String(length=36), nullable=True),
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
        sa.ForeignKeyConstraint(['payee_id'], ['payees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_income_schedules_user_id', 'income_schedules', ['user_id'])
    op.create_index('ix_income_schedules_payee_id', 'income_schedules', ['payee_id'])
    migrate_expected_income(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_income_schedules_payee_id', table_name='income_schedules')
    op.drop_index('ix_income_schedules_user_id', table_name='income_schedules')
    op.drop_table('income_schedules')
