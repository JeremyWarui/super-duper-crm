"""Online meetings, who attended them, and the devices that take call alerts.

Revision ID: meetings_push
Revises: sms_queue
Create Date: 2026-11-23 23:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "meetings_push"
down_revision: str | None = "sms_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('push_subscriptions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('endpoint', sa.Text(), nullable=False),
    sa.Column('p256dh', sa.String(length=200), nullable=False),
    sa.Column('auth', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_push_subscriptions_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_push_subscriptions')),
    sa.UniqueConstraint('endpoint', name=op.f('uq_push_subscriptions_endpoint'))
    )
    op.create_table('meetings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('campaign_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('mode', sa.String(length=10), nullable=False),
    sa.Column('host_id', sa.Uuid(), nullable=True),
    sa.Column('ward_id', sa.Uuid(), nullable=True),
    sa.Column('event_id', sa.Uuid(), nullable=True),
    sa.Column('livekit_room', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], name=op.f('fk_meetings_campaign_id_campaigns'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], name=op.f('fk_meetings_event_id_events'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['host_id'], ['users.id'], name=op.f('fk_meetings_host_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], name=op.f('fk_meetings_ward_id_wards'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_meetings')),
    sa.UniqueConstraint('livekit_room', name=op.f('uq_meetings_livekit_room'))
    )
    op.create_index(op.f('ix_meetings_campaign_id'), 'meetings', ['campaign_id'], unique=False)
    op.create_table('meeting_attendance',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('meeting_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], name=op.f('fk_meeting_attendance_meeting_id_meetings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_meeting_attendance_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_meeting_attendance'))
    )
    op.create_index(op.f('ix_meeting_attendance_meeting_id'), 'meeting_attendance', ['meeting_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_meeting_attendance_meeting_id'), table_name='meeting_attendance')
    op.drop_table('meeting_attendance')
    op.drop_index(op.f('ix_meetings_campaign_id'), table_name='meetings')
    op.drop_table('meetings')
    op.drop_table('push_subscriptions')
