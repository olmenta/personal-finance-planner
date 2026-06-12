"""one active onboarding session per user

Concurrent POST /onboarding/start calls (e.g. React StrictMode double-firing
in dev) could create two active sessions and fork the interview. Abandon any
duplicates (keeping the oldest) and enforce uniqueness with a partial index.

Revision ID: 43666f3761ac
Revises: 10b7a5ed7972
Create Date: 2026-06-12 13:45:11.194038

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43666f3761ac'
down_revision: Union[str, Sequence[str], None] = '10b7a5ed7972'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Defensive dedupe so the unique index can build: keep each user's oldest
    # active session, abandon the rest.
    op.execute(
        sa.text(
            """
            UPDATE onboarding_sessions
            SET status = 'abandoned'
            WHERE status = 'active'
              AND id NOT IN (
                SELECT DISTINCT ON (user_id) id
                FROM onboarding_sessions
                WHERE status = 'active'
                ORDER BY user_id, created_at
              )
            """
        )
    )
    op.create_index(
        "uq_onboarding_one_active_per_user",
        "onboarding_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_onboarding_one_active_per_user", table_name="onboarding_sessions")
