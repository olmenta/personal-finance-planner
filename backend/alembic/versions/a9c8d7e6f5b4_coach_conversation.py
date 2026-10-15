"""coach conversation, messages and actions

Revision ID: a9c8d7e6f5b4
Revises: f1a2b3c4d5e6
Create Date: 2026-10-14 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a9c8d7e6f5b4'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'coach_conversations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_table(
        'coach_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=12), nullable=False),
        sa.Column('text', sa.String(length=8000), nullable=False),
        sa.Column('widgets', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('client_message_id', sa.String(length=64), nullable=True),
        sa.Column('reply_to', sa.String(length=36), nullable=True),
        sa.Column('snapshot_version', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['coach_conversations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_coach_messages_client_id', 'coach_messages', ['user_id', 'client_message_id'],
                    unique=True, postgresql_where=sa.text('client_message_id IS NOT NULL'))
    op.create_index('ix_coach_messages_conversation_created', 'coach_messages', ['conversation_id', 'created_at'])
    op.create_table(
        'coach_actions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('message_id', sa.String(length=36), nullable=True),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('command', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('preview', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('revision', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('undone_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_coach_actions_user_id', 'coach_actions', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_coach_actions_user_id', table_name='coach_actions')
    op.drop_table('coach_actions')
    op.drop_index('ix_coach_messages_conversation_created', table_name='coach_messages')
    op.drop_index('uq_coach_messages_client_id', table_name='coach_messages')
    op.drop_table('coach_messages')
    op.drop_table('coach_conversations')
