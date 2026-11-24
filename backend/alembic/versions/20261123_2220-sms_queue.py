"""The bulk SMS queue: one run per approved message, one outbox row per number, and the
language a message is declared in.

Revision ID: sms_queue
Revises: competitive_targets
Create Date: 2026-11-23 22:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "sms_queue"
down_revision: str | None = "competitive_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('sms_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('campaign_id', sa.Uuid(), nullable=False),
    sa.Column('message_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('language', sa.String(length=2), nullable=False),
    sa.Column('sender_name', sa.String(length=150), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('vetting_ref', sa.String(length=100), nullable=False),
    sa.Column('vetted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('targeted', sa.Integer(), nullable=False),
    sa.Column('excluded_no_consent', sa.Integer(), nullable=False),
    sa.Column('excluded_opted_out', sa.Integer(), nullable=False),
    sa.Column('sent', sa.Integer(), nullable=False),
    sa.Column('failed', sa.Integer(), nullable=False),
    sa.Column('segments', sa.Integer(), nullable=False),
    sa.Column('estimated_cost_cents', sa.Integer(), nullable=False),
    sa.Column('actual_cost_cents', sa.Integer(), nullable=False),
    sa.Column('approved_by_id', sa.Uuid(), nullable=True),
    sa.Column('halted_by_id', sa.Uuid(), nullable=True),
    sa.Column('halt_reason', sa.Text(), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['approved_by_id'], ['users.id'], name=op.f('fk_sms_runs_approved_by_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], name=op.f('fk_sms_runs_campaign_id_campaigns'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['halted_by_id'], ['users.id'], name=op.f('fk_sms_runs_halted_by_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['message_id'], ['campaign_messages.id'], name=op.f('fk_sms_runs_message_id_campaign_messages'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sms_runs')),
    sa.UniqueConstraint('message_id', name=op.f('uq_sms_runs_message_id'))
    )
    op.create_index(op.f('ix_sms_runs_campaign_id'), 'sms_runs', ['campaign_id'], unique=False)
    op.create_table('sms_outbox',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('supporter_id', sa.Uuid(), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('skip_reason', sa.String(length=40), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sms_log_id', sa.Uuid(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('batch_key', sa.String(length=64), server_default='', nullable=False),
    sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['sms_runs.id'], name=op.f('fk_sms_outbox_run_id_sms_runs'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sms_log_id'], ['sms_log.id'], name=op.f('fk_sms_outbox_sms_log_id_sms_log'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['supporter_id'], ['supporters.id'], name=op.f('fk_sms_outbox_supporter_id_supporters'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sms_outbox')),
    sa.UniqueConstraint('run_id', 'phone', name='uq_sms_outbox_run_phone')
    )
    op.create_index(op.f('ix_sms_outbox_run_id'), 'sms_outbox', ['run_id'], unique=False)
    op.create_index(op.f('ix_sms_outbox_status'), 'sms_outbox', ['status'], unique=False)
    op.add_column('campaign_messages', sa.Column('language', sa.String(length=2), server_default='en', nullable=False))


def downgrade() -> None:
    op.drop_column('campaign_messages', 'language')
    op.drop_index(op.f('ix_sms_outbox_status'), table_name='sms_outbox')
    op.drop_index(op.f('ix_sms_outbox_run_id'), table_name='sms_outbox')
    op.drop_table('sms_outbox')
    op.drop_index(op.f('ix_sms_runs_campaign_id'), table_name='sms_runs')
    op.drop_table('sms_runs')
