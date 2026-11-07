"""The schema: every table, index and constraint, and the party settings row.

Its ID is shared with no earlier revision, so a database built from an earlier
chain stops `alembic upgrade head` instead of passing as up to date.

Revision ID: schema_20261107
Revises:
Create Date: 2026-11-07 16:23:51.212773

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "schema_20261107"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agenda_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("summary", sa.String(length=300), server_default="", nullable=False),
        sa.Column("what_we_will_do", sa.Text(), server_default="", nullable=False),
        sa.Column("why_it_matters", sa.Text(), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agenda_issues")),
    )
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backup_runs")),
    )
    op.create_table(
        "counties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("registered_voters", sa.Integer(), nullable=True),
        sa.Column("turnout_2022_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("retired", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "registered_voters IS NULL OR registered_voters >= 0",
            name=op.f("ck_counties_registered_voters_non_negative"),
        ),
        sa.CheckConstraint(
            "turnout_2022_pct IS NULL OR (turnout_2022_pct >= 0 AND turnout_2022_pct <= 100)",
            name=op.f("ck_counties_turnout_pct_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_counties")),
    )
    op.create_index(op.f("ix_counties_name"), "counties", ["name"], unique=False)
    op.create_table(
        "email_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("to", sa.String(length=254), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_log")),
    )
    op.create_index(op.f("ix_email_log_to"), "email_log", ["to"], unique=False)
    op.create_table(
        "party_organs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("text", sa.String(length=300), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_organs")),
    )
    op.create_table(
        "party_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "join",
                "withdraw",
                "volunteer_withdraw",
                name="party_request_kind",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_requests")),
    )
    op.create_index("ix_party_requests_created_at", "party_requests", ["created_at"], unique=False)
    op.create_table(
        "party_settings",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column(
            "registration_number",
            sa.String(length=40),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "founded_year", sa.String(length=4), server_default=sa.text("''"), nullable=False
        ),
        sa.Column("aspirant_steps", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_party_settings_singleton")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_settings")),
    )
    op.create_table(
        "party_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("text", sa.String(length=300), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_values")),
    )
    op.create_table(
        "party_videos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=500), server_default="", nullable=False),
        sa.Column("duration", sa.String(length=8), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_videos")),
    )
    op.create_table(
        "primary_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "seat",
            sa.Enum(
                "mca",
                "mp",
                "governor",
                "senator",
                "women_rep",
                name="seat",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("area", sa.String(length=150), nullable=False),
        sa.Column("candidate", sa.String(length=150), nullable=False),
        sa.Column("votes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("declared_on", sa.Date(), nullable=True),
        sa.Column("demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("votes >= 0", name=op.f("ck_primary_results_votes_not_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_primary_results")),
    )
    op.create_table(
        "reconcile_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("checked", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconcile_runs")),
    )
    op.create_table(
        "setup_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_setup_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_setup_tokens_token_hash")),
    )
    op.create_table(
        "sms_inbound",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("to", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sms_inbound")),
        sa.UniqueConstraint("provider_id", name=op.f("uq_sms_inbound_provider_id")),
    )
    op.create_table(
        "subscribers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact", sa.String(length=254), nullable=False),
        sa.Column("channel", sa.String(length=10), nullable=False),
        sa.Column("consent_wording", sa.Text(), nullable=False),
        sa.Column("notice_version", sa.String(length=20), nullable=False),
        sa.Column("unsubscribe_code", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("channel IN ('sms', 'email')", name=op.f("ck_subscribers_channel")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscribers")),
        sa.UniqueConstraint("contact", name=op.f("uq_subscribers_contact")),
        sa.UniqueConstraint("unsubscribe_code", name=op.f("uq_subscribers_unsubscribe_code")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("first_name", sa.String(length=150), nullable=False),
        sa.Column("last_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "candidate",
                "manager",
                "coordinator",
                "comms",
                "mobilizer",
                "agent",
                name="user_role",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column(
            "kind",
            sa.Enum(
                "campaign",
                "staff",
                "member",
                name="user_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("party_member_id", sa.Uuid(), nullable=True),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("pending", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(kind = 'campaign') = (role IS NOT NULL)", name=op.f("ck_users_kind_matches_role")
        ),
        sa.CheckConstraint(
            "NOT (pending AND is_active)", name=op.f("ck_users_pending_is_inactive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("id", "kind", name=op.f("uq_users_id_kind")),
        sa.UniqueConstraint("id", "role", name=op.f("uq_users_id_role")),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_index(
        "uq_users_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email <> ''"),
        sqlite_where=sa.text("email <> ''"),
    )
    op.create_index(
        "uq_users_member_login",
        "users",
        ["party_member_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'member'"),
        sqlite_where=sa.text("kind = 'member'"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_name", sa.String(length=150), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_events_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)
    op.create_index(
        "ix_audit_events_subject_type_subject_id",
        "audit_events",
        ["subject_type", "subject_id"],
        unique=False,
    )
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("handoff_hash", sa.String(length=64), nullable=True),
        sa.Column("handoff_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_tokens")),
        sa.UniqueConstraint("handoff_hash", name=op.f("uq_auth_tokens_handoff_hash")),
        sa.UniqueConstraint("user_id", name=op.f("uq_auth_tokens_user_id")),
    )
    op.create_index(op.f("ix_auth_tokens_key"), "auth_tokens", ["key"], unique=True)
    op.create_table(
        "branches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("county_id", sa.Uuid(), nullable=False),
        sa.Column("office_address", sa.String(length=300), server_default="", nullable=False),
        sa.Column("phone", sa.String(length=20), server_default="", nullable=False),
        sa.Column("email", sa.String(length=254), server_default="", nullable=False),
        sa.Column("next_meeting_on", sa.Date(), nullable=True),
        sa.Column("next_meeting_venue", sa.String(length=150), server_default="", nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_branches_county_id_counties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branches")),
        sa.UniqueConstraint("county_id", name=op.f("uq_branches_county_id")),
    )
    op.create_table(
        "constituencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("county_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("retired", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_constituencies_county_id_counties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_constituencies")),
    )
    op.create_index(
        op.f("ix_constituencies_county_id"), "constituencies", ["county_id"], unique=False
    )
    op.create_index(op.f("ix_constituencies_name"), "constituencies", ["name"], unique=False)
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_import_runs_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_runs")),
    )
    op.create_table(
        "login_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum(
                "invite",
                "reset",
                name="link_purpose",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_login_invites_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_login_invites_token_hash")),
    )
    op.create_index(op.f("ix_login_invites_user_id"), "login_invites", ["user_id"], unique=False)
    op.create_table(
        "nomination_windows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("opens_on", sa.Date(), nullable=False),
        sa.Column("closes_on", sa.Date(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("drafted_by_id", sa.Uuid(), nullable=True),
        sa.Column("published_by_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["drafted_by_id"],
            ["users.id"],
            name=op.f("fk_nomination_windows_drafted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_id"],
            ["users.id"],
            name=op.f("fk_nomination_windows_published_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nomination_windows")),
    )
    op.create_index(
        op.f("ix_nomination_windows_status"), "nomination_windows", ["status"], unique=False
    )
    op.create_table(
        "party_posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "news",
                "event",
                name="post_kind",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("venue", sa.String(length=150), nullable=False),
        sa.Column(
            "label",
            sa.Enum(
                "statement",
                "news",
                "opinion",
                name="post_label",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="news",
            nullable=False,
        ),
        sa.Column("place", sa.String(length=80), server_default="", nullable=False),
        sa.Column("author", sa.String(length=150), server_default="", nullable=False),
        sa.Column("author_photo_url", sa.String(length=500), server_default="", nullable=False),
        sa.Column("reference", sa.String(length=40), server_default="", nullable=False),
        sa.Column("pdf_url", sa.String(length=500), server_default="", nullable=False),
        sa.Column("county_id", sa.Uuid(), nullable=True),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(kind = 'event') = (event_date IS NOT NULL)",
            name=op.f("ck_party_posts_event_has_date"),
        ),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_party_posts_county_id_counties"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_posts")),
    )
    op.create_index(
        "ix_party_posts_kind_published_event_date",
        "party_posts",
        ["kind", "published", "event_date"],
        unique=False,
    )
    op.create_index(
        "ix_party_posts_kind_published_published_on",
        "party_posts",
        ["kind", "published", "published_on"],
        unique=False,
    )
    op.create_table(
        "party_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=8), server_default="staff", nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "membership_officer",
                "nominations_officer",
                "comms_officer",
                name="party_role",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("kind = 'staff'", name=op.f("ck_party_roles_kind_is_staff")),
        sa.ForeignKeyConstraint(
            ["user_id", "kind"],
            ["users.id", "users.kind"],
            name=op.f("fk_party_roles_user_id_kind_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role", name=op.f("pk_party_roles")),
    )
    op.create_table(
        "stored_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "area",
            sa.Enum(
                "site",
                "slides",
                "leaders",
                "documents",
                "candidates",
                "minutes",
                "nominations",
                name="file_area",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("public", sa.Boolean(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("widths", sa.JSON(), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name=op.f("fk_stored_files_uploaded_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stored_files")),
    )
    op.create_index(op.f("ix_stored_files_sha256"), "stored_files", ["sha256"], unique=False)
    op.create_table(
        "hero_slides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("image_url", sa.String(length=500), server_default="", nullable=False),
        sa.Column("image_file_id", sa.Uuid(), nullable=True),
        sa.Column("kicker", sa.String(length=80), server_default="", nullable=False),
        sa.Column("headline", sa.String(length=120), nullable=False),
        sa.Column("line", sa.String(length=300), server_default="", nullable=False),
        sa.Column("button_label", sa.String(length=40), server_default="", nullable=False),
        sa.Column("button_url", sa.String(length=500), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["image_file_id"],
            ["stored_files.id"],
            name=op.f("fk_hero_slides_image_file_id_stored_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hero_slides")),
    )
    op.create_table(
        "import_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("change", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["import_runs.id"],
            name=op.f("fk_import_changes_run_id_import_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_changes")),
    )
    op.create_index(op.f("ix_import_changes_run_id"), "import_changes", ["run_id"], unique=False)
    op.create_table(
        "nomination_seats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("window_id", sa.Uuid(), nullable=False),
        sa.Column(
            "seat",
            sa.Enum(
                "mca",
                "mp",
                "governor",
                "senator",
                "women_rep",
                name="seat",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("fee_kes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["window_id"],
            ["nomination_windows.id"],
            name=op.f("fk_nomination_seats_window_id_nomination_windows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nomination_seats")),
        sa.UniqueConstraint("window_id", "seat", name="uq_nomination_seats_window_seat"),
    )
    op.create_index(
        op.f("ix_nomination_seats_window_id"), "nomination_seats", ["window_id"], unique=False
    )
    op.create_table(
        "party_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["stored_files.id"],
            name=op.f("fk_party_documents_file_id_stored_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_documents")),
    )
    op.create_table(
        "party_leaders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("position", sa.String(length=150), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("photo_url", sa.String(length=500), nullable=False),
        sa.Column("photo_file_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["photo_file_id"],
            ["stored_files.id"],
            name=op.f("fk_party_leaders_photo_file_id_stored_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_leaders")),
    )
    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column(
            "organisation_type",
            sa.Enum(
                "party",
                "aspirant",
                name="organisation_type",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("short_name", sa.String(length=30), nullable=False),
        sa.Column("slogan", sa.String(length=150), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "about_headline", sa.String(length=150), server_default=sa.text("''"), nullable=False
        ),
        sa.Column("logo_url", sa.String(length=500), nullable=False),
        sa.Column("logo_file_id", sa.Uuid(), nullable=True),
        sa.Column("primary_colour", sa.String(length=7), nullable=False),
        sa.Column("secondary_colour", sa.String(length=7), nullable=False),
        sa.Column("contact_email", sa.String(length=254), nullable=False),
        sa.Column("contact_phone", sa.String(length=20), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column("social_links", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("manifesto_text", sa.Text(), nullable=False),
        sa.Column("manifesto_url", sa.String(length=500), nullable=False),
        sa.Column("privacy_notice", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("payment_instructions", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "mpesa_paybill", sa.String(length=10), server_default=sa.text("''"), nullable=False
        ),
        sa.Column(
            "mpesa_account", sa.String(length=20), server_default=sa.text("''"), nullable=False
        ),
        sa.Column("mpesa_till", sa.String(length=10), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "privacy_notice_version",
            sa.String(length=20),
            server_default=sa.text("'1'"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "length(primary_colour) = 7 AND substr(primary_colour, 1, 1) = '#' AND lower(substr(primary_colour, 2, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(primary_colour, 3, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(primary_colour, 4, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(primary_colour, 5, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(primary_colour, 6, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(primary_colour, 7, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f')",
            name=op.f("ck_site_settings_primary_colour_hex"),
        ),
        sa.CheckConstraint(
            "length(secondary_colour) = 7 AND substr(secondary_colour, 1, 1) = '#' AND lower(substr(secondary_colour, 2, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(secondary_colour, 3, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(secondary_colour, 4, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(secondary_colour, 5, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(secondary_colour, 6, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f') AND lower(substr(secondary_colour, 7, 1)) IN ('0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f')",
            name=op.f("ck_site_settings_secondary_colour_hex"),
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_site_settings_singleton")),
        sa.ForeignKeyConstraint(
            ["logo_file_id"],
            ["stored_files.id"],
            name=op.f("fk_site_settings_logo_file_id_stored_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_settings")),
    )
    op.create_table(
        "wards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("constituency_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("registered_voters", sa.Integer(), nullable=True),
        sa.Column("retired", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "registered_voters IS NULL OR registered_voters >= 0",
            name=op.f("ck_wards_registered_voters_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["constituency_id"],
            ["constituencies.id"],
            name=op.f("fk_wards_constituency_id_constituencies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wards")),
    )
    op.create_index(op.f("ix_wards_constituency_id"), "wards", ["constituency_id"], unique=False)
    op.create_index(op.f("ix_wards_name"), "wards", ["name"], unique=False)
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "party",
                "hosted",
                "standalone",
                name="workspace_kind",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "office_level",
            sa.Enum(
                "ward",
                "constituency",
                "county",
                "national",
                name="office_level",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "seat",
            sa.Enum(
                "mca",
                "mp",
                "governor",
                "senator",
                "women_rep",
                name="seat",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("county_id", sa.Uuid(), nullable=True),
        sa.Column("constituency_id", sa.Uuid(), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("election_date", sa.Date(), nullable=True),
        sa.Column("signup_code", sa.String(length=24), nullable=False),
        sa.Column("signups_open", sa.Boolean(), nullable=False),
        sa.Column("team_code", sa.String(length=24), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_id", sa.Uuid(), nullable=True),
        sa.Column("retention_months", sa.Integer(), server_default=sa.text("6"), nullable=False),
        sa.Column("supporters_erased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(kind = 'party' AND seat IS NULL AND office_level = 'national') OR (kind <> 'party' AND seat IS NOT NULL AND ((seat = 'mca' AND office_level = 'ward') OR (seat = 'mp' AND office_level = 'constituency') OR (seat IN ('governor', 'senator', 'women_rep') AND office_level = 'county')))",
            name=op.f("ck_campaigns_seat_matches_scope"),
        ),
        sa.ForeignKeyConstraint(
            ["closed_by_id"],
            ["users.id"],
            name=op.f("fk_campaigns_closed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["constituency_id"],
            ["constituencies.id"],
            name=op.f("fk_campaigns_constituency_id_constituencies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_campaigns_county_id_counties"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_campaigns_ward_id_wards"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns")),
        sa.UniqueConstraint("signup_code", name=op.f("uq_campaigns_signup_code")),
        sa.UniqueConstraint("team_code", name=op.f("uq_campaigns_team_code")),
    )
    op.create_index(
        op.f("ix_campaigns_constituency_id"), "campaigns", ["constituency_id"], unique=False
    )
    op.create_index(op.f("ix_campaigns_county_id"), "campaigns", ["county_id"], unique=False)
    op.create_index(op.f("ix_campaigns_ward_id"), "campaigns", ["ward_id"], unique=False)
    op.create_index(
        "uq_campaigns_one_party_one_standalone",
        "campaigns",
        ["kind"],
        unique=True,
        postgresql_where=sa.text("kind <> 'hosted'"),
        sqlite_where=sa.text("kind <> 'hosted'"),
    )
    op.create_table(
        "party_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=20), nullable=False),
        sa.Column("county_id", sa.Uuid(), nullable=True),
        sa.Column("constituency_id", sa.Uuid(), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("drafted_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("targeted", sa.Integer(), nullable=False),
        sa.Column("recipients", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["constituency_id"],
            ["constituencies.id"],
            name=op.f("fk_party_messages_constituency_id_constituencies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_party_messages_county_id_counties"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_party_messages_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["drafted_by_id"],
            ["users.id"],
            name=op.f("fk_party_messages_drafted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_party_messages_ward_id_wards"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_messages")),
    )
    op.create_index(op.f("ix_party_messages_status"), "party_messages", ["status"], unique=False)
    op.create_table(
        "registration_centres",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("registered_voters", sa.Integer(), nullable=True),
        sa.Column("retired", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "registered_voters IS NULL OR registered_voters >= 0",
            name=op.f("ck_registration_centres_registered_voters_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_registration_centres_ward_id_wards"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registration_centres")),
    )
    op.create_index(
        op.f("ix_registration_centres_ward_id"), "registration_centres", ["ward_id"], unique=False
    )
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "applied",
                "vetted",
                "trained",
                "ready",
                name="agent_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("training_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_agents_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_agents_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_agents_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_agents_ward_id_wards"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents")),
        sa.UniqueConstraint("user_id", name=op.f("uq_agents_user_id")),
    )
    op.create_index(op.f("ix_agents_campaign_id"), "agents", ["campaign_id"], unique=False)
    op.create_index(
        op.f("ix_agents_registration_centre_id"), "agents", ["registration_centre_id"], unique=False
    )
    op.create_index(op.f("ix_agents_ward_id"), "agents", ["ward_id"], unique=False)
    op.create_table(
        "campaign_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "candidate",
                "manager",
                "coordinator",
                "comms",
                "mobilizer",
                "agent",
                name="member_role",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_members_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "role"],
            ["users.id", "users.role"],
            name=op.f("fk_campaign_members_user_id_role_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_members")),
    )
    op.create_index(
        op.f("ix_campaign_members_campaign_id"), "campaign_members", ["campaign_id"], unique=False
    )
    op.create_index(
        "uq_campaign_members_one_campaign_per_user", "campaign_members", ["user_id"], unique=True
    )
    op.create_index(
        "uq_campaign_members_one_candidate",
        "campaign_members",
        ["campaign_id"],
        unique=True,
        postgresql_where=sa.text("role = 'candidate'"),
        sqlite_where=sa.text("role = 'candidate'"),
    )
    op.create_index(
        "uq_campaign_members_one_manager",
        "campaign_members",
        ["campaign_id"],
        unique=True,
        postgresql_where=sa.text("role = 'manager'"),
        sqlite_where=sa.text("role = 'manager'"),
    )
    op.create_table(
        "campaign_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("wards", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("drafted_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("recipients", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_messages_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_campaign_messages_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["drafted_by_id"],
            ["users.id"],
            name=op.f("fk_campaign_messages_drafted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_messages")),
    )
    op.create_index(
        op.f("ix_campaign_messages_campaign_id"), "campaign_messages", ["campaign_id"], unique=False
    )
    op.create_table(
        "campaign_sharing",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("event_reach", sa.Boolean(), nullable=False),
        sa.Column("ward_coverage", sa.Boolean(), nullable=False),
        sa.Column("supporter_counts", sa.Boolean(), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_sharing_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["users.id"],
            name=op.f("fk_campaign_sharing_changed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("campaign_id", name=op.f("pk_campaign_sharing")),
    )
    op.create_table(
        "data_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "access",
                "correction",
                "erasure",
                name="data_request_kind",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("requester_name", sa.String(length=150), nullable=False),
        sa.Column("requester_contact", sa.String(length=254), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "done",
                name="data_request_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("logged_by_id", sa.Uuid(), nullable=True),
        sa.Column("answered_by_id", sa.Uuid(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["answered_by_id"],
            ["users.id"],
            name=op.f("fk_data_requests_answered_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_data_requests_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["logged_by_id"],
            ["users.id"],
            name=op.f("fk_data_requests_logged_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_requests")),
    )
    op.create_index(
        op.f("ix_data_requests_campaign_id"), "data_requests", ["campaign_id"], unique=False
    )
    op.create_table(
        "mobilizers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_mobilizers_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_mobilizers_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_mobilizers_user_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_mobilizers_ward_id_wards"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mobilizers")),
        sa.UniqueConstraint("user_id", name=op.f("uq_mobilizers_user_id")),
    )
    op.create_index(op.f("ix_mobilizers_campaign_id"), "mobilizers", ["campaign_id"], unique=False)
    op.create_index(
        op.f("ix_mobilizers_registration_centre_id"),
        "mobilizers",
        ["registration_centre_id"],
        unique=False,
    )
    op.create_index(op.f("ix_mobilizers_ward_id"), "mobilizers", ["ward_id"], unique=False)
    op.create_index(
        "uq_mobilizers_campaign_registration_centre",
        "mobilizers",
        ["campaign_id", "registration_centre_id"],
        unique=True,
        postgresql_where=sa.text("registration_centre_id IS NOT NULL"),
        sqlite_where=sa.text("registration_centre_id IS NOT NULL"),
    )
    op.create_index(
        "uq_mobilizers_campaign_ward",
        "mobilizers",
        ["campaign_id", "ward_id"],
        unique=True,
        postgresql_where=sa.text("ward_id IS NOT NULL AND registration_centre_id IS NULL"),
        sqlite_where=sa.text("ward_id IS NOT NULL AND registration_centre_id IS NULL"),
    )
    op.create_table(
        "sms_opt_outs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_sms_opt_outs_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sms_opt_outs")),
    )
    op.create_index(op.f("ix_sms_opt_outs_phone"), "sms_opt_outs", ["phone"], unique=False)
    op.create_index(
        "uq_sms_opt_outs_campaign",
        "sms_opt_outs",
        ["phone", "campaign_id"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NOT NULL"),
        sqlite_where=sa.text("campaign_id IS NOT NULL"),
    )
    op.create_index(
        "uq_sms_opt_outs_everywhere",
        "sms_opt_outs",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NULL"),
        sqlite_where=sa.text("campaign_id IS NULL"),
    )
    op.create_table(
        "targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("projected_turnout_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("registered_voters", sa.Integer(), nullable=True),
        sa.Column("votes_needed", sa.Integer(), nullable=True),
        sa.Column("votes_committed", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "projected_turnout_pct IS NULL OR (projected_turnout_pct >= 0 AND projected_turnout_pct <= 100)",
            name=op.f("ck_targets_projected_turnout_pct_range"),
        ),
        sa.CheckConstraint(
            "votes_committed >= 0", name=op.f("ck_targets_votes_committed_non_negative")
        ),
        sa.CheckConstraint(
            "votes_needed IS NULL OR votes_needed >= 0",
            name=op.f("ck_targets_votes_needed_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_targets_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_targets_registration_centre_id_registration_centres"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_targets_ward_id_wards"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_targets")),
    )
    op.create_index(op.f("ix_targets_campaign_id"), "targets", ["campaign_id"], unique=False)
    op.create_index(
        op.f("ix_targets_registration_centre_id"),
        "targets",
        ["registration_centre_id"],
        unique=False,
    )
    op.create_index(op.f("ix_targets_ward_id"), "targets", ["ward_id"], unique=False)
    op.create_index(
        "uq_targets_campaign_registration_centre",
        "targets",
        ["campaign_id", "registration_centre_id"],
        unique=True,
        postgresql_where=sa.text("registration_centre_id IS NOT NULL"),
        sqlite_where=sa.text("registration_centre_id IS NOT NULL"),
    )
    op.create_index(
        "uq_targets_campaign_ward",
        "targets",
        ["campaign_id", "ward_id"],
        unique=True,
        postgresql_where=sa.text("registration_centre_id IS NULL"),
        sqlite_where=sa.text("registration_centre_id IS NULL"),
    )
    op.create_table(
        "team_registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "role",
            sa.Enum(
                "mobilizer",
                "agent",
                name="field_role",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("first_name", sa.String(length=150), nullable=False),
        sa.Column("last_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("id_number", sa.String(length=20), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("consent_wording", sa.Text(), nullable=False),
        sa.Column("consent_version", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                name="registration_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_team_registrations_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_team_registrations_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_team_registrations_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_team_registrations_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_team_registrations_ward_id_wards"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_registrations")),
        sa.UniqueConstraint("user_id", name=op.f("uq_team_registrations_user_id")),
    )
    op.create_index(
        op.f("ix_team_registrations_campaign_id"),
        "team_registrations",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "uq_team_registrations_campaign_id_number",
        "team_registrations",
        ["campaign_id", "id_number"],
        unique=True,
        postgresql_where=sa.text("status != 'rejected'"),
        sqlite_where=sa.text("status != 'rejected'"),
    )
    op.create_index(
        "uq_team_registrations_campaign_phone",
        "team_registrations",
        ["campaign_id", "phone"],
        unique=True,
        postgresql_where=sa.text("status != 'rejected'"),
        sqlite_where=sa.text("status != 'rejected'"),
    )
    op.create_table(
        "campaign_member_areas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_member_id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(ward_id IS NULL) <> (registration_centre_id IS NULL)",
            name=op.f("ck_campaign_member_areas_one_place"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_member_id"],
            ["campaign_members.id"],
            name=op.f("fk_campaign_member_areas_campaign_member_id_campaign_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_campaign_member_areas_registration_centre_id_registration_centres"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_campaign_member_areas_ward_id_wards"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_member_areas")),
        sa.UniqueConstraint(
            "campaign_member_id",
            "registration_centre_id",
            name=op.f("uq_campaign_member_areas_campaign_member_id_registration_centre_id"),
        ),
        sa.UniqueConstraint(
            "campaign_member_id",
            "ward_id",
            name=op.f("uq_campaign_member_areas_campaign_member_id_ward_id"),
        ),
    )
    op.create_index(
        op.f("ix_campaign_member_areas_campaign_member_id"),
        "campaign_member_areas",
        ["campaign_member_id"],
        unique=False,
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("mobilizer_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("venue", sa.String(length=150), nullable=False),
        sa.Column("scheduled_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "planned",
                "done",
                "cancelled",
                name="event_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("signup_code", sa.String(length=24), nullable=False),
        sa.Column("signups_open", sa.Boolean(), nullable=False),
        sa.Column("number_reached", sa.Integer(), nullable=False),
        sa.Column("number_attended", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "number_attended >= 0", name=op.f("ck_events_number_attended_non_negative")
        ),
        sa.CheckConstraint(
            "number_reached >= 0", name=op.f("ck_events_number_reached_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_events_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mobilizer_id"],
            ["mobilizers.id"],
            name=op.f("fk_events_mobilizer_id_mobilizers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_events_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_events_ward_id_wards"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        sa.UniqueConstraint("signup_code", name=op.f("uq_events_signup_code")),
    )
    op.create_index(op.f("ix_events_campaign_id"), "events", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_events_mobilizer_id"), "events", ["mobilizer_id"], unique=False)
    op.create_index(
        op.f("ix_events_registration_centre_id"), "events", ["registration_centre_id"], unique=False
    )
    op.create_index(op.f("ix_events_scheduled_date"), "events", ["scheduled_date"], unique=False)
    op.create_index(op.f("ix_events_ward_id"), "events", ["ward_id"], unique=False)
    op.create_table(
        "party_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("first_name", sa.String(length=75), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "suspended",
                "withdrawn",
                name="party_member_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("consent_wording", sa.Text(), nullable=False),
        sa.Column(
            "consent_channel",
            sa.Enum(
                "web_form",
                "officer_entry",
                name="party_consent_channel",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sms_consent_wording", sa.Text(), nullable=True),
        sa.Column("sms_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdraw_code", sa.String(length=32), nullable=True),
        sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recruited_by_id", sa.Uuid(), nullable=True),
        sa.Column("recruitment_county_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "consent_wording <> ''", name=op.f("ck_party_members_consent_wording_not_empty")
        ),
        sa.CheckConstraint(
            "length(trim(full_name)) > 0", name=op.f("ck_party_members_full_name_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_party_members_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["recruited_by_id"],
            ["campaign_members.id"],
            name=op.f("fk_party_members_recruited_by_id_campaign_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["recruitment_county_id"],
            ["counties.id"],
            name=op.f("fk_party_members_recruitment_county_id_counties"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_party_members_registration_centre_id_registration_centres"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_party_members_ward_id_wards"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_members")),
        sa.UniqueConstraint("phone", name="uq_party_members_phone"),
        sa.UniqueConstraint("withdraw_code", name=op.f("uq_party_members_withdraw_code")),
    )
    op.create_index(
        op.f("ix_party_members_full_name"), "party_members", ["full_name"], unique=False
    )
    op.create_index(
        op.f("ix_party_members_recruited_by_id"), "party_members", ["recruited_by_id"], unique=False
    )
    op.create_index(op.f("ix_party_members_status"), "party_members", ["status"], unique=False)
    op.create_index(op.f("ix_party_members_ward_id"), "party_members", ["ward_id"], unique=False)
    op.create_table(
        "recruitment_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_member_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_member_id"],
            ["campaign_members.id"],
            name=op.f("fk_recruitment_codes_campaign_member_id_campaign_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recruitment_codes")),
        sa.UniqueConstraint("code", name=op.f("uq_recruitment_codes_code")),
    )
    op.create_index(
        op.f("ix_recruitment_codes_campaign_member_id"),
        "recruitment_codes",
        ["campaign_member_id"],
        unique=False,
    )
    op.create_index(
        "uq_recruitment_codes_one_active",
        "recruitment_codes",
        ["campaign_member_id"],
        unique=True,
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active"),
    )
    op.create_table(
        "aspirants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column(
            "seat",
            sa.Enum(
                "mca",
                "mp",
                "governor",
                "senator",
                "women_rep",
                name="seat",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("county_id", sa.Uuid(), nullable=True),
        sa.Column("constituency_id", sa.Uuid(), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "submitted",
                "approved",
                "rejected",
                "withdrawn",
                "suspended",
                name="aspirant_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("window_id", sa.Uuid(), nullable=True),
        sa.Column("fee_kes", sa.Integer(), nullable=False),
        sa.Column("fee_paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fee_reference", sa.String(length=50), nullable=False),
        sa.Column("fee_marked_by_id", sa.Uuid(), nullable=True),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(seat = 'mca' AND ward_id IS NOT NULL AND constituency_id IS NULL AND county_id IS NULL) OR (seat = 'mp' AND constituency_id IS NOT NULL AND ward_id IS NULL AND county_id IS NULL) OR (seat IN ('governor', 'senator', 'women_rep') AND county_id IS NOT NULL AND ward_id IS NULL AND constituency_id IS NULL)",
            name=op.f("ck_aspirants_area_matches_seat"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_aspirants_campaign_id_campaigns"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["constituency_id"],
            ["constituencies.id"],
            name=op.f("fk_aspirants_constituency_id_constituencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_aspirants_county_id_counties"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_aspirants_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_aspirants_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fee_marked_by_id"],
            ["users.id"],
            name=op.f("fk_aspirants_fee_marked_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["party_members.id"],
            name=op.f("fk_aspirants_member_id_party_members"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_aspirants_ward_id_wards"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["window_id"],
            ["nomination_windows.id"],
            name=op.f("fk_aspirants_window_id_nomination_windows"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aspirants")),
        sa.UniqueConstraint("campaign_id", name="uq_aspirants_campaign_id"),
    )
    op.create_index(op.f("ix_aspirants_member_id"), "aspirants", ["member_id"], unique=False)
    op.create_index(op.f("ix_aspirants_seat"), "aspirants", ["seat"], unique=False)
    op.create_index(op.f("ix_aspirants_status"), "aspirants", ["status"], unique=False)
    op.create_index(
        "uq_aspirants_one_live_per_member",
        "aspirants",
        ["member_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('draft', 'submitted', 'approved', 'suspended')"),
        postgresql_where=sa.text("status IN ('draft', 'submitted', 'approved', 'suspended')"),
    )
    op.create_table(
        "assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("mobilizer_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "event",
                "ward_work",
                "activity",
                name="assignment_kind",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_kes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "assigned",
                "done",
                "cancelled",
                name="assignment_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("done_by_id", sa.Uuid(), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(mobilizer_id IS NULL) <> (agent_id IS NULL)", name=op.f("ck_assignments_one_member")
        ),
        sa.CheckConstraint("amount_kes > 0", name=op.f("ck_assignments_amount_kes_positive")),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_assignments_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_assignments_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_assignments_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["done_by_id"],
            ["users.id"],
            name=op.f("fk_assignments_done_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_assignments_event_id_events"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["mobilizer_id"],
            ["mobilizers.id"],
            name=op.f("fk_assignments_mobilizer_id_mobilizers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_assignments_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_assignments_ward_id_wards"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
    )
    op.create_index(op.f("ix_assignments_agent_id"), "assignments", ["agent_id"], unique=False)
    op.create_index(
        op.f("ix_assignments_campaign_id"), "assignments", ["campaign_id"], unique=False
    )
    op.create_index(op.f("ix_assignments_event_id"), "assignments", ["event_id"], unique=False)
    op.create_index(
        op.f("ix_assignments_mobilizer_id"), "assignments", ["mobilizer_id"], unique=False
    )
    op.create_index(op.f("ix_assignments_ward_id"), "assignments", ["ward_id"], unique=False)
    op.create_table(
        "branch_officials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column(
            "office",
            sa.Enum(
                "chair",
                "secretary",
                "treasurer",
                "organising_secretary",
                "youth_leader",
                "women_leader",
                "other",
                name="branch_office",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=80), server_default="", nullable=False),
        sa.Column("holder_name", sa.String(length=150), nullable=False),
        sa.Column("term_start", sa.Date(), nullable=False),
        sa.Column("term_end", sa.Date(), nullable=True),
        sa.Column(
            "start_reason",
            sa.Enum(
                "elected",
                "interim",
                "recorded",
                name="term_start_reason",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "end_reason",
            sa.Enum(
                "replaced",
                "resigned",
                "removed",
                "completed",
                name="term_end_reason",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("minutes_file_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("appointed_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "term_end IS NULL OR term_end >= term_start",
            name=op.f("ck_branch_officials_term_in_order"),
        ),
        sa.ForeignKeyConstraint(
            ["appointed_by_id"],
            ["users.id"],
            name=op.f("fk_branch_officials_appointed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_branch_officials_branch_id_branches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["party_members.id"],
            name=op.f("fk_branch_officials_member_id_party_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["minutes_file_id"],
            ["stored_files.id"],
            name=op.f("fk_branch_officials_minutes_file_id_stored_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branch_officials")),
    )
    op.create_index(
        op.f("ix_branch_officials_branch_id"), "branch_officials", ["branch_id"], unique=False
    )
    op.create_index(
        op.f("ix_branch_officials_member_id"), "branch_officials", ["member_id"], unique=False
    )
    op.create_index(
        "uq_branch_officials_open_term",
        "branch_officials",
        ["branch_id", "office"],
        unique=True,
        postgresql_where=sa.text("term_end IS NULL AND office <> 'other'"),
        sqlite_where=sa.text("term_end IS NULL AND office <> 'other'"),
    )
    op.create_table(
        "sms_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("party_message_id", sa.Uuid(), nullable=True),
        sa.Column("sender_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_sms_log_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_sms_log_event_id_events"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["campaign_messages.id"],
            name=op.f("fk_sms_log_message_id_campaign_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["party_message_id"],
            ["party_messages.id"],
            name=op.f("fk_sms_log_party_message_id_party_messages"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            name=op.f("fk_sms_log_sender_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sms_log")),
        sa.UniqueConstraint("provider_id", name=op.f("uq_sms_log_provider_id")),
    )
    op.create_index(op.f("ix_sms_log_campaign_id"), "sms_log", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_sms_log_event_id"), "sms_log", ["event_id"], unique=False)
    op.create_index(op.f("ix_sms_log_message_id"), "sms_log", ["message_id"], unique=False)
    op.create_index(
        op.f("ix_sms_log_party_message_id"), "sms_log", ["party_message_id"], unique=False
    )
    op.create_index(op.f("ix_sms_log_phone"), "sms_log", ["phone"], unique=False)
    op.create_table(
        "supporters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("mobilizer_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column(
            "support_level",
            sa.Enum(
                "supporter",
                "undecided",
                "opposed",
                name="support_level",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("consent_given", sa.Boolean(), nullable=False),
        sa.Column(
            "consent_channel",
            sa.Enum(
                "event_qr",
                "campaign_link",
                "mobilizer",
                name="consent_channel",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("consent_wording", sa.Text(), nullable=True),
        sa.Column("withdraw_code", sa.String(length=32), nullable=True),
        sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_supporters_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_supporters_event_id_events"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["mobilizer_id"],
            ["mobilizers.id"],
            name=op.f("fk_supporters_mobilizer_id_mobilizers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_supporters_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_supporters_ward_id_wards"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supporters")),
        sa.UniqueConstraint("withdraw_code", name=op.f("uq_supporters_withdraw_code")),
    )
    op.create_index(op.f("ix_supporters_campaign_id"), "supporters", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_supporters_event_id"), "supporters", ["event_id"], unique=False)
    op.create_index(
        op.f("ix_supporters_mobilizer_id"), "supporters", ["mobilizer_id"], unique=False
    )
    op.create_index(
        op.f("ix_supporters_registration_centre_id"),
        "supporters",
        ["registration_centre_id"],
        unique=False,
    )
    op.create_index(op.f("ix_supporters_ward_id"), "supporters", ["ward_id"], unique=False)
    op.create_index(
        "uq_supporters_campaign_phone",
        "supporters",
        ["campaign_id", "phone"],
        unique=True,
        postgresql_where=sa.text("phone <> ''"),
        sqlite_where=sa.text("phone <> ''"),
    )
    op.create_table(
        "volunteer_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("first_name", sa.String(length=75), nullable=False),
        sa.Column("last_name", sa.String(length=75), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column(
            "profession",
            sa.Enum(
                "farmer",
                "teacher",
                "business",
                "student",
                "other",
                name="profession",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("profession_other", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "interested",
                "active",
                "inactive",
                "withdrawn",
                name="volunteer_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("interest_other", sa.String(length=100), nullable=False),
        sa.Column("availability_notes", sa.Text(), nullable=True),
        sa.Column(
            "preferred_contact",
            sa.Enum(
                "call",
                "sms",
                "whatsapp",
                "email",
                name="contact_method",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("consent_wording", sa.Text(), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdraw_code", sa.String(length=32), nullable=True),
        sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "consent_wording <> ''", name=op.f("ck_volunteer_profiles_consent_wording_not_empty")
        ),
        sa.CheckConstraint(
            "(campaign_id IS NULL) = (member_id IS NOT NULL)",
            name=op.f("ck_volunteer_profiles_owner"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_volunteer_profiles_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["party_members.id"],
            name=op.f("fk_volunteer_profiles_member_id_party_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_volunteer_profiles_registration_centre_id_registration_centres"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_volunteer_profiles_ward_id_wards"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_volunteer_profiles")),
        sa.UniqueConstraint("campaign_id", "phone", name="uq_volunteer_profiles_campaign_phone"),
        sa.UniqueConstraint("member_id", name="uq_volunteer_profiles_member_id"),
        sa.UniqueConstraint("withdraw_code", name=op.f("uq_volunteer_profiles_withdraw_code")),
    )
    op.create_index(
        "ix_volunteer_profiles_campaign_id_status",
        "volunteer_profiles",
        ["campaign_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_volunteer_profiles_ward_id"), "volunteer_profiles", ["ward_id"], unique=False
    )
    op.create_index(
        "uq_volunteer_profiles_party_phone",
        "volunteer_profiles",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NULL"),
        sqlite_where=sa.text("campaign_id IS NULL"),
    )
    op.create_table(
        "aspirant_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aspirant_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["aspirant_id"],
            ["aspirants.id"],
            name=op.f("fk_aspirant_documents_aspirant_id_aspirants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["stored_files.id"],
            name=op.f("fk_aspirant_documents_file_id_stored_files"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aspirant_documents")),
    )
    op.create_index(
        op.f("ix_aspirant_documents_aspirant_id"),
        "aspirant_documents",
        ["aspirant_id"],
        unique=False,
    )
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("aspirant_id", sa.Uuid(), nullable=True),
        sa.Column("photo_url", sa.String(length=500), server_default="", nullable=False),
        sa.Column("photo_file_id", sa.Uuid(), nullable=True),
        sa.Column("slogan", sa.String(length=120), server_default="", nullable=False),
        sa.Column("bio", sa.Text(), server_default="", nullable=False),
        sa.Column("priorities", sa.JSON(), nullable=False),
        sa.Column("office_address", sa.String(length=300), server_default="", nullable=False),
        sa.Column("office_phone", sa.String(length=20), server_default="", nullable=False),
        sa.Column("office_email", sa.String(length=254), server_default="", nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["aspirant_id"],
            ["aspirants.id"],
            name=op.f("fk_candidate_profiles_aspirant_id_aspirants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_candidate_profiles_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["photo_file_id"],
            ["stored_files.id"],
            name=op.f("fk_candidate_profiles_photo_file_id_stored_files"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_profiles")),
        sa.UniqueConstraint("aspirant_id", name=op.f("uq_candidate_profiles_aspirant_id")),
        sa.UniqueConstraint("campaign_id", name=op.f("uq_candidate_profiles_campaign_id")),
    )
    op.create_table(
        "party_post_aspirants",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("aspirant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["aspirant_id"],
            ["aspirants.id"],
            name=op.f("fk_party_post_aspirants_aspirant_id_aspirants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["party_posts.id"],
            name=op.f("fk_party_post_aspirants_post_id_party_posts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("post_id", "aspirant_id", name=op.f("pk_party_post_aspirants")),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("mobilizer_id", sa.Uuid(), nullable=True),
        sa.Column("event_title", sa.String(length=150), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "approver_role",
            sa.Enum(
                "candidate",
                "manager",
                "coordinator",
                "comms",
                "mobilizer",
                "agent",
                name="approver_role",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_name", sa.String(length=150), nullable=False),
        sa.Column("recipient_phone", sa.String(length=20), nullable=False),
        sa.Column("amount_kes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled",
                "sending",
                "paid",
                "failed",
                "cancelled",
                name="payment_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.String(length=200), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sending_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount_kes > 0", name=op.f("ck_payments_amount_kes_positive")),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_payments_agent_id_agents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_id"],
            ["users.id"],
            name=op.f("fk_payments_approved_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name=op.f("fk_payments_assignment_id_assignments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_payments_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_payments_event_id_events"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["mobilizer_id"],
            ["mobilizers.id"],
            name=op.f("fk_payments_mobilizer_id_mobilizers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["scheduled_by_id"],
            ["users.id"],
            name=op.f("fk_payments_scheduled_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
    )
    op.create_index(op.f("ix_payments_agent_id"), "payments", ["agent_id"], unique=False)
    op.create_index(op.f("ix_payments_assignment_id"), "payments", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_payments_campaign_id"), "payments", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_payments_event_id"), "payments", ["event_id"], unique=False)
    op.create_index(op.f("ix_payments_mobilizer_id"), "payments", ["mobilizer_id"], unique=False)
    op.create_index(op.f("ix_payments_reference"), "payments", ["reference"], unique=False)
    op.create_index(
        "uq_payments_assignment",
        "payments",
        ["assignment_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
        sqlite_where=sa.text("status <> 'cancelled'"),
    )
    op.create_index(
        "uq_payments_event_mobilizer",
        "payments",
        ["event_id", "mobilizer_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
        sqlite_where=sa.text("status <> 'cancelled'"),
    )
    op.create_table(
        "payments_in",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum(
                "nomination_fee",
                "contribution",
                name="pay_in_purpose",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "method",
            sa.Enum(
                "stk",
                "manual",
                name="pay_in_method",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "paid",
                "to_confirm",
                "failed",
                "rejected",
                name="pay_in_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("aspirant_id", sa.Uuid(), nullable=True),
        sa.Column("amount_kes", sa.Integer(), nullable=False),
        sa.Column("payer_name", sa.String(length=150), nullable=False),
        sa.Column("payer_phone", sa.String(length=20), nullable=False),
        sa.Column("payer_email", sa.String(length=254), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("mpesa_code", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["aspirant_id"],
            ["aspirants.id"],
            name=op.f("fk_payments_in_aspirant_id_aspirants"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_payments_in_campaign_id_campaigns"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_payments_in_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments_in")),
        sa.UniqueConstraint("reference", name=op.f("uq_payments_in_reference")),
    )
    op.create_index(
        op.f("ix_payments_in_aspirant_id"), "payments_in", ["aspirant_id"], unique=False
    )
    op.create_index(
        op.f("ix_payments_in_campaign_id"), "payments_in", ["campaign_id"], unique=False
    )
    op.create_index(op.f("ix_payments_in_status"), "payments_in", ["status"], unique=False)
    op.create_table(
        "reconcile_differences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("reference", sa.String(length=100), nullable=False),
        sa.Column("ledger", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_reconcile_differences_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_reconcile_differences_payment_id_payments"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["reconcile_runs.id"],
            name=op.f("fk_reconcile_differences_run_id_reconcile_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconcile_differences")),
    )
    op.create_index(
        op.f("ix_reconcile_differences_campaign_id"),
        "reconcile_differences",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconcile_differences_payment_id"),
        "reconcile_differences",
        ["payment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconcile_differences_run_id"), "reconcile_differences", ["run_id"], unique=False
    )

    # users and party_members point at each other, so this key comes last.
    with op.batch_alter_table("users") as batch:
        batch.create_foreign_key(
            op.f("fk_users_party_member_id_party_members"),
            "party_members",
            ["party_member_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute("INSERT INTO party_settings (id) VALUES (1)")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint(op.f("fk_users_party_member_id_party_members"), type_="foreignkey")
    op.drop_index(op.f("ix_reconcile_differences_run_id"), table_name="reconcile_differences")
    op.drop_index(op.f("ix_reconcile_differences_payment_id"), table_name="reconcile_differences")
    op.drop_index(op.f("ix_reconcile_differences_campaign_id"), table_name="reconcile_differences")
    op.drop_table("reconcile_differences")
    op.drop_index(op.f("ix_payments_in_status"), table_name="payments_in")
    op.drop_index(op.f("ix_payments_in_campaign_id"), table_name="payments_in")
    op.drop_index(op.f("ix_payments_in_aspirant_id"), table_name="payments_in")
    op.drop_table("payments_in")
    op.drop_index(
        "uq_payments_event_mobilizer",
        table_name="payments",
        postgresql_where=sa.text("status <> 'cancelled'"),
        sqlite_where=sa.text("status <> 'cancelled'"),
    )
    op.drop_index(
        "uq_payments_assignment",
        table_name="payments",
        postgresql_where=sa.text("status <> 'cancelled'"),
        sqlite_where=sa.text("status <> 'cancelled'"),
    )
    op.drop_index(op.f("ix_payments_reference"), table_name="payments")
    op.drop_index(op.f("ix_payments_mobilizer_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_event_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_campaign_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_assignment_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_agent_id"), table_name="payments")
    op.drop_table("payments")
    op.drop_table("party_post_aspirants")
    op.drop_table("candidate_profiles")
    op.drop_index(op.f("ix_aspirant_documents_aspirant_id"), table_name="aspirant_documents")
    op.drop_table("aspirant_documents")
    op.drop_index(
        "uq_volunteer_profiles_party_phone",
        table_name="volunteer_profiles",
        postgresql_where=sa.text("campaign_id IS NULL"),
        sqlite_where=sa.text("campaign_id IS NULL"),
    )
    op.drop_index(op.f("ix_volunteer_profiles_ward_id"), table_name="volunteer_profiles")
    op.drop_index("ix_volunteer_profiles_campaign_id_status", table_name="volunteer_profiles")
    op.drop_table("volunteer_profiles")
    op.drop_index(
        "uq_supporters_campaign_phone",
        table_name="supporters",
        postgresql_where=sa.text("phone <> ''"),
        sqlite_where=sa.text("phone <> ''"),
    )
    op.drop_index(op.f("ix_supporters_ward_id"), table_name="supporters")
    op.drop_index(op.f("ix_supporters_registration_centre_id"), table_name="supporters")
    op.drop_index(op.f("ix_supporters_mobilizer_id"), table_name="supporters")
    op.drop_index(op.f("ix_supporters_event_id"), table_name="supporters")
    op.drop_index(op.f("ix_supporters_campaign_id"), table_name="supporters")
    op.drop_table("supporters")
    op.drop_index(op.f("ix_sms_log_phone"), table_name="sms_log")
    op.drop_index(op.f("ix_sms_log_party_message_id"), table_name="sms_log")
    op.drop_index(op.f("ix_sms_log_message_id"), table_name="sms_log")
    op.drop_index(op.f("ix_sms_log_event_id"), table_name="sms_log")
    op.drop_index(op.f("ix_sms_log_campaign_id"), table_name="sms_log")
    op.drop_table("sms_log")
    op.drop_index(
        "uq_branch_officials_open_term",
        table_name="branch_officials",
        postgresql_where=sa.text("term_end IS NULL AND office <> 'other'"),
        sqlite_where=sa.text("term_end IS NULL AND office <> 'other'"),
    )
    op.drop_index(op.f("ix_branch_officials_member_id"), table_name="branch_officials")
    op.drop_index(op.f("ix_branch_officials_branch_id"), table_name="branch_officials")
    op.drop_table("branch_officials")
    op.drop_index(op.f("ix_assignments_ward_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_mobilizer_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_event_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_campaign_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_agent_id"), table_name="assignments")
    op.drop_table("assignments")
    op.drop_index(
        "uq_aspirants_one_live_per_member",
        table_name="aspirants",
        sqlite_where=sa.text("status IN ('draft', 'submitted', 'approved', 'suspended')"),
        postgresql_where=sa.text("status IN ('draft', 'submitted', 'approved', 'suspended')"),
    )
    op.drop_index(op.f("ix_aspirants_status"), table_name="aspirants")
    op.drop_index(op.f("ix_aspirants_seat"), table_name="aspirants")
    op.drop_index(op.f("ix_aspirants_member_id"), table_name="aspirants")
    op.drop_table("aspirants")
    op.drop_index(
        "uq_recruitment_codes_one_active",
        table_name="recruitment_codes",
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active"),
    )
    op.drop_index(op.f("ix_recruitment_codes_campaign_member_id"), table_name="recruitment_codes")
    op.drop_table("recruitment_codes")
    op.drop_index(op.f("ix_party_members_ward_id"), table_name="party_members")
    op.drop_index(op.f("ix_party_members_status"), table_name="party_members")
    op.drop_index(op.f("ix_party_members_recruited_by_id"), table_name="party_members")
    op.drop_index(op.f("ix_party_members_full_name"), table_name="party_members")
    op.drop_table("party_members")
    op.drop_index(op.f("ix_events_ward_id"), table_name="events")
    op.drop_index(op.f("ix_events_scheduled_date"), table_name="events")
    op.drop_index(op.f("ix_events_registration_centre_id"), table_name="events")
    op.drop_index(op.f("ix_events_mobilizer_id"), table_name="events")
    op.drop_index(op.f("ix_events_campaign_id"), table_name="events")
    op.drop_table("events")
    op.drop_index(
        op.f("ix_campaign_member_areas_campaign_member_id"), table_name="campaign_member_areas"
    )
    op.drop_table("campaign_member_areas")
    op.drop_index(
        "uq_team_registrations_campaign_phone",
        table_name="team_registrations",
        postgresql_where=sa.text("status != 'rejected'"),
        sqlite_where=sa.text("status != 'rejected'"),
    )
    op.drop_index(
        "uq_team_registrations_campaign_id_number",
        table_name="team_registrations",
        postgresql_where=sa.text("status != 'rejected'"),
        sqlite_where=sa.text("status != 'rejected'"),
    )
    op.drop_index(op.f("ix_team_registrations_campaign_id"), table_name="team_registrations")
    op.drop_table("team_registrations")
    op.drop_index(
        "uq_targets_campaign_ward",
        table_name="targets",
        postgresql_where=sa.text("registration_centre_id IS NULL"),
        sqlite_where=sa.text("registration_centre_id IS NULL"),
    )
    op.drop_index(
        "uq_targets_campaign_registration_centre",
        table_name="targets",
        postgresql_where=sa.text("registration_centre_id IS NOT NULL"),
        sqlite_where=sa.text("registration_centre_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_targets_ward_id"), table_name="targets")
    op.drop_index(op.f("ix_targets_registration_centre_id"), table_name="targets")
    op.drop_index(op.f("ix_targets_campaign_id"), table_name="targets")
    op.drop_table("targets")
    op.drop_index(
        "uq_sms_opt_outs_everywhere",
        table_name="sms_opt_outs",
        postgresql_where=sa.text("campaign_id IS NULL"),
        sqlite_where=sa.text("campaign_id IS NULL"),
    )
    op.drop_index(
        "uq_sms_opt_outs_campaign",
        table_name="sms_opt_outs",
        postgresql_where=sa.text("campaign_id IS NOT NULL"),
        sqlite_where=sa.text("campaign_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_sms_opt_outs_phone"), table_name="sms_opt_outs")
    op.drop_table("sms_opt_outs")
    op.drop_index(
        "uq_mobilizers_campaign_ward",
        table_name="mobilizers",
        postgresql_where=sa.text("ward_id IS NOT NULL AND registration_centre_id IS NULL"),
        sqlite_where=sa.text("ward_id IS NOT NULL AND registration_centre_id IS NULL"),
    )
    op.drop_index(
        "uq_mobilizers_campaign_registration_centre",
        table_name="mobilizers",
        postgresql_where=sa.text("registration_centre_id IS NOT NULL"),
        sqlite_where=sa.text("registration_centre_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_mobilizers_ward_id"), table_name="mobilizers")
    op.drop_index(op.f("ix_mobilizers_registration_centre_id"), table_name="mobilizers")
    op.drop_index(op.f("ix_mobilizers_campaign_id"), table_name="mobilizers")
    op.drop_table("mobilizers")
    op.drop_index(op.f("ix_data_requests_campaign_id"), table_name="data_requests")
    op.drop_table("data_requests")
    op.drop_table("campaign_sharing")
    op.drop_index(op.f("ix_campaign_messages_campaign_id"), table_name="campaign_messages")
    op.drop_table("campaign_messages")
    op.drop_index(
        "uq_campaign_members_one_manager",
        table_name="campaign_members",
        postgresql_where=sa.text("role = 'manager'"),
        sqlite_where=sa.text("role = 'manager'"),
    )
    op.drop_index(
        "uq_campaign_members_one_candidate",
        table_name="campaign_members",
        postgresql_where=sa.text("role = 'candidate'"),
        sqlite_where=sa.text("role = 'candidate'"),
    )
    op.drop_index("uq_campaign_members_one_campaign_per_user", table_name="campaign_members")
    op.drop_index(op.f("ix_campaign_members_campaign_id"), table_name="campaign_members")
    op.drop_table("campaign_members")
    op.drop_index(op.f("ix_agents_ward_id"), table_name="agents")
    op.drop_index(op.f("ix_agents_registration_centre_id"), table_name="agents")
    op.drop_index(op.f("ix_agents_campaign_id"), table_name="agents")
    op.drop_table("agents")
    op.drop_index(op.f("ix_registration_centres_ward_id"), table_name="registration_centres")
    op.drop_table("registration_centres")
    op.drop_index(op.f("ix_party_messages_status"), table_name="party_messages")
    op.drop_table("party_messages")
    op.drop_index(
        "uq_campaigns_one_party_one_standalone",
        table_name="campaigns",
        postgresql_where=sa.text("kind <> 'hosted'"),
        sqlite_where=sa.text("kind <> 'hosted'"),
    )
    op.drop_index(op.f("ix_campaigns_ward_id"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_county_id"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_constituency_id"), table_name="campaigns")
    op.drop_table("campaigns")
    op.drop_index(op.f("ix_wards_name"), table_name="wards")
    op.drop_index(op.f("ix_wards_constituency_id"), table_name="wards")
    op.drop_table("wards")
    op.drop_table("site_settings")
    op.drop_table("party_leaders")
    op.drop_table("party_documents")
    op.drop_index(op.f("ix_nomination_seats_window_id"), table_name="nomination_seats")
    op.drop_table("nomination_seats")
    op.drop_index(op.f("ix_import_changes_run_id"), table_name="import_changes")
    op.drop_table("import_changes")
    op.drop_table("hero_slides")
    op.drop_index(op.f("ix_stored_files_sha256"), table_name="stored_files")
    op.drop_table("stored_files")
    op.drop_table("party_roles")
    op.drop_index("ix_party_posts_kind_published_published_on", table_name="party_posts")
    op.drop_index("ix_party_posts_kind_published_event_date", table_name="party_posts")
    op.drop_table("party_posts")
    op.drop_index(op.f("ix_nomination_windows_status"), table_name="nomination_windows")
    op.drop_table("nomination_windows")
    op.drop_index(op.f("ix_login_invites_user_id"), table_name="login_invites")
    op.drop_table("login_invites")
    op.drop_table("import_runs")
    op.drop_index(op.f("ix_constituencies_name"), table_name="constituencies")
    op.drop_index(op.f("ix_constituencies_county_id"), table_name="constituencies")
    op.drop_table("constituencies")
    op.drop_table("branches")
    op.drop_index(op.f("ix_auth_tokens_key"), table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_index("ix_audit_events_subject_type_subject_id", table_name="audit_events")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(
        "uq_users_member_login",
        table_name="users",
        postgresql_where=sa.text("kind = 'member'"),
        sqlite_where=sa.text("kind = 'member'"),
    )
    op.drop_index(
        "uq_users_email",
        table_name="users",
        postgresql_where=sa.text("email <> ''"),
        sqlite_where=sa.text("email <> ''"),
    )
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
    op.drop_table("subscribers")
    op.drop_table("sms_inbound")
    op.drop_table("setup_tokens")
    op.drop_table("reconcile_runs")
    op.drop_table("primary_results")
    op.drop_table("party_videos")
    op.drop_table("party_values")
    op.drop_table("party_settings")
    op.drop_index("ix_party_requests_created_at", table_name="party_requests")
    op.drop_table("party_requests")
    op.drop_table("party_organs")
    op.drop_index(op.f("ix_email_log_to"), table_name="email_log")
    op.drop_table("email_log")
    op.drop_index(op.f("ix_counties_name"), table_name="counties")
    op.drop_table("counties")
    op.drop_table("backup_runs")
    op.drop_table("agenda_issues")
