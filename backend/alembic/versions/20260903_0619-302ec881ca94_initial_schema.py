"""initial schema

Revision ID: 302ec881ca94
Revises: 
Create Date: 2026-09-03 06:19:10.026038

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '302ec881ca94'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('counties',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('registered_voters', sa.Integer(), nullable=True),
    sa.Column('turnout_2022_pct', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.CheckConstraint('registered_voters IS NULL OR registered_voters >= 0', name=op.f('ck_counties_registered_voters_non_negative')),
    sa.CheckConstraint('turnout_2022_pct IS NULL OR (turnout_2022_pct >= 0 AND turnout_2022_pct <= 100)', name=op.f('ck_counties_turnout_pct_range')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_counties'))
    )
    op.create_index(op.f('ix_counties_name'), 'counties', ['name'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('username', sa.String(length=150), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('first_name', sa.String(length=150), nullable=False),
    sa.Column('last_name', sa.String(length=150), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('role', sa.Enum('candidate', 'manager', 'mobilizer', name='user_role', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('password_hash', sa.String(length=128), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('constituencies',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('county_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.ForeignKeyConstraint(['county_id'], ['counties.id'], name=op.f('fk_constituencies_county_id_counties'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_constituencies'))
    )
    op.create_index(op.f('ix_constituencies_county_id'), 'constituencies', ['county_id'], unique=False)
    op.create_index(op.f('ix_constituencies_name'), 'constituencies', ['name'], unique=False)
    op.create_table('wards',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('constituency_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('registered_voters', sa.Integer(), nullable=True),
    sa.CheckConstraint('registered_voters IS NULL OR registered_voters >= 0', name=op.f('ck_wards_registered_voters_non_negative')),
    sa.ForeignKeyConstraint(['constituency_id'], ['constituencies.id'], name=op.f('fk_wards_constituency_id_constituencies'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_wards'))
    )
    op.create_index(op.f('ix_wards_constituency_id'), 'wards', ['constituency_id'], unique=False)
    op.create_index(op.f('ix_wards_name'), 'wards', ['name'], unique=False)
    op.create_table('campaigns',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('office_level', sa.Enum('ward', 'constituency', 'county', name='office_level', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('county_id', sa.Uuid(), nullable=True),
    sa.Column('constituency_id', sa.Uuid(), nullable=True),
    sa.Column('ward_id', sa.Uuid(), nullable=True),
    sa.Column('election_date', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['users.id'], name=op.f('fk_campaigns_candidate_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['constituency_id'], ['constituencies.id'], name=op.f('fk_campaigns_constituency_id_constituencies'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['county_id'], ['counties.id'], name=op.f('fk_campaigns_county_id_counties'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], name=op.f('fk_campaigns_ward_id_wards'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_campaigns'))
    )
    op.create_index(op.f('ix_campaigns_candidate_id'), 'campaigns', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_campaigns_constituency_id'), 'campaigns', ['constituency_id'], unique=False)
    op.create_index(op.f('ix_campaigns_county_id'), 'campaigns', ['county_id'], unique=False)
    op.create_index(op.f('ix_campaigns_ward_id'), 'campaigns', ['ward_id'], unique=False)
    op.create_table('polling_stations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ward_id', sa.Uuid(), nullable=False),
    sa.Column('centre_code', sa.String(length=30), nullable=False),
    sa.Column('centre_name', sa.String(length=200), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('registered_voters', sa.Integer(), nullable=True),
    sa.CheckConstraint('registered_voters IS NULL OR registered_voters >= 0', name=op.f('ck_polling_stations_registered_voters_non_negative')),
    sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], name=op.f('fk_polling_stations_ward_id_wards'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_polling_stations'))
    )
    op.create_index(op.f('ix_polling_stations_ward_id'), 'polling_stations', ['ward_id'], unique=False)
    op.create_table('registration_centres',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ward_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('registered_voters', sa.Integer(), nullable=True),
    sa.CheckConstraint('registered_voters IS NULL OR registered_voters >= 0', name=op.f('ck_registration_centres_registered_voters_non_negative')),
    sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], name=op.f('fk_registration_centres_ward_id_wards'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_registration_centres'))
    )
    op.create_index(op.f('ix_registration_centres_ward_id'), 'registration_centres', ['ward_id'], unique=False)
    op.create_table('mobilizers',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('campaign_id', sa.Uuid(), nullable=False),
    sa.Column('ward_id', sa.Uuid(), nullable=False),
    sa.Column('registration_centre_id', sa.Uuid(), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], name=op.f('fk_mobilizers_campaign_id_campaigns'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['registration_centre_id'], ['registration_centres.id'], name=op.f('fk_mobilizers_registration_centre_id_registration_centres'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_mobilizers_user_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], name=op.f('fk_mobilizers_ward_id_wards'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_mobilizers')),
    sa.UniqueConstraint('user_id', name=op.f('uq_mobilizers_user_id'))
    )
    op.create_index(op.f('ix_mobilizers_campaign_id'), 'mobilizers', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_mobilizers_registration_centre_id'), 'mobilizers', ['registration_centre_id'], unique=False)
    op.create_index(op.f('ix_mobilizers_ward_id'), 'mobilizers', ['ward_id'], unique=False)
    op.create_table('targets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('campaign_id', sa.Uuid(), nullable=False),
    sa.Column('ward_id', sa.Uuid(), nullable=False),
    sa.Column('registration_centre_id', sa.Uuid(), nullable=True),
    sa.Column('projected_turnout_pct', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('votes_needed', sa.Integer(), nullable=True),
    sa.Column('votes_committed', sa.Integer(), nullable=False),
    sa.CheckConstraint('projected_turnout_pct IS NULL OR (projected_turnout_pct >= 0 AND projected_turnout_pct <= 100)', name=op.f('ck_targets_projected_turnout_pct_range')),
    sa.CheckConstraint('votes_committed >= 0', name=op.f('ck_targets_votes_committed_non_negative')),
    sa.CheckConstraint('votes_needed IS NULL OR votes_needed >= 0', name=op.f('ck_targets_votes_needed_non_negative')),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], name=op.f('fk_targets_campaign_id_campaigns'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['registration_centre_id'], ['registration_centres.id'], name=op.f('fk_targets_registration_centre_id_registration_centres'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], name=op.f('fk_targets_ward_id_wards'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_targets'))
    )
    op.create_index(op.f('ix_targets_campaign_id'), 'targets', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_targets_registration_centre_id'), 'targets', ['registration_centre_id'], unique=False)
    op.create_index(op.f('ix_targets_ward_id'), 'targets', ['ward_id'], unique=False)
    op.create_index('uq_targets_campaign_registration_centre', 'targets', ['campaign_id', 'registration_centre_id'], unique=True, postgresql_where=sa.text('registration_centre_id IS NOT NULL'), sqlite_where=sa.text('registration_centre_id IS NOT NULL'))
    op.create_index('uq_targets_campaign_ward', 'targets', ['campaign_id', 'ward_id'], unique=True, postgresql_where=sa.text('registration_centre_id IS NULL'), sqlite_where=sa.text('registration_centre_id IS NULL'))
    op.create_table('events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('campaign_id', sa.Uuid(), nullable=False),
    sa.Column('ward_id', sa.Uuid(), nullable=False),
    sa.Column('registration_centre_id', sa.Uuid(), nullable=True),
    sa.Column('mobilizer_id', sa.Uuid(), nullable=True),
    sa.Column('title', sa.String(length=150), nullable=False),
    sa.Column('venue', sa.String(length=150), nullable=False),
    sa.Column('scheduled_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.Enum('planned', 'done', 'cancelled', name='event_status', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('number_reached', sa.Integer(), nullable=False),
    sa.Column('number_attended', sa.Integer(), nullable=False),
    sa.CheckConstraint('number_attended >= 0', name=op.f('ck_events_number_attended_non_negative')),
    sa.CheckConstraint('number_reached >= 0', name=op.f('ck_events_number_reached_non_negative')),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], name=op.f('fk_events_campaign_id_campaigns'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['mobilizer_id'], ['mobilizers.id'], name=op.f('fk_events_mobilizer_id_mobilizers'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['registration_centre_id'], ['registration_centres.id'], name=op.f('fk_events_registration_centre_id_registration_centres'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], name=op.f('fk_events_ward_id_wards'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_events'))
    )
    op.create_index(op.f('ix_events_campaign_id'), 'events', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_events_mobilizer_id'), 'events', ['mobilizer_id'], unique=False)
    op.create_index(op.f('ix_events_registration_centre_id'), 'events', ['registration_centre_id'], unique=False)
    op.create_index(op.f('ix_events_scheduled_date'), 'events', ['scheduled_date'], unique=False)
    op.create_index(op.f('ix_events_ward_id'), 'events', ['ward_id'], unique=False)
    op.create_table('supporters',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('campaign_id', sa.Uuid(), nullable=False),
    sa.Column('ward_id', sa.Uuid(), nullable=True),
    sa.Column('mobilizer_id', sa.Uuid(), nullable=True),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('support_level', sa.Enum('supporter', 'undecided', 'opposed', name='support_level', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('consent_given', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], name=op.f('fk_supporters_campaign_id_campaigns'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['mobilizer_id'], ['mobilizers.id'], name=op.f('fk_supporters_mobilizer_id_mobilizers'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['ward_id'], ['wards.id'], name=op.f('fk_supporters_ward_id_wards'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_supporters'))
    )
    op.create_index(op.f('ix_supporters_campaign_id'), 'supporters', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_supporters_mobilizer_id'), 'supporters', ['mobilizer_id'], unique=False)
    op.create_index(op.f('ix_supporters_ward_id'), 'supporters', ['ward_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_supporters_ward_id'), table_name='supporters')
    op.drop_index(op.f('ix_supporters_mobilizer_id'), table_name='supporters')
    op.drop_index(op.f('ix_supporters_campaign_id'), table_name='supporters')
    op.drop_table('supporters')
    op.drop_index(op.f('ix_events_ward_id'), table_name='events')
    op.drop_index(op.f('ix_events_scheduled_date'), table_name='events')
    op.drop_index(op.f('ix_events_registration_centre_id'), table_name='events')
    op.drop_index(op.f('ix_events_mobilizer_id'), table_name='events')
    op.drop_index(op.f('ix_events_campaign_id'), table_name='events')
    op.drop_table('events')
    op.drop_index('uq_targets_campaign_ward', table_name='targets', postgresql_where=sa.text('registration_centre_id IS NULL'), sqlite_where=sa.text('registration_centre_id IS NULL'))
    op.drop_index('uq_targets_campaign_registration_centre', table_name='targets', postgresql_where=sa.text('registration_centre_id IS NOT NULL'), sqlite_where=sa.text('registration_centre_id IS NOT NULL'))
    op.drop_index(op.f('ix_targets_ward_id'), table_name='targets')
    op.drop_index(op.f('ix_targets_registration_centre_id'), table_name='targets')
    op.drop_index(op.f('ix_targets_campaign_id'), table_name='targets')
    op.drop_table('targets')
    op.drop_index(op.f('ix_mobilizers_ward_id'), table_name='mobilizers')
    op.drop_index(op.f('ix_mobilizers_registration_centre_id'), table_name='mobilizers')
    op.drop_index(op.f('ix_mobilizers_campaign_id'), table_name='mobilizers')
    op.drop_table('mobilizers')
    op.drop_index(op.f('ix_registration_centres_ward_id'), table_name='registration_centres')
    op.drop_table('registration_centres')
    op.drop_index(op.f('ix_polling_stations_ward_id'), table_name='polling_stations')
    op.drop_table('polling_stations')
    op.drop_index(op.f('ix_campaigns_ward_id'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_county_id'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_constituency_id'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_candidate_id'), table_name='campaigns')
    op.drop_table('campaigns')
    op.drop_index(op.f('ix_wards_name'), table_name='wards')
    op.drop_index(op.f('ix_wards_constituency_id'), table_name='wards')
    op.drop_table('wards')
    op.drop_index(op.f('ix_constituencies_name'), table_name='constituencies')
    op.drop_index(op.f('ix_constituencies_county_id'), table_name='constituencies')
    op.drop_table('constituencies')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_counties_name'), table_name='counties')
    op.drop_table('counties')
