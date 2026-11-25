"""One install is one aspirant's campaign: the party tables, columns and choices go, and the
website's posts, documents and videos take neutral names.

Revision ID: aspirant_only
Revises: issue_image
"""

import sqlalchemy as sa
from alembic import op

revision: str = "aspirant_only"
down_revision: str | None = "issue_image"
branch_labels = None
depends_on = None

PARTY_TABLES = [
    "party_post_aspirants",
    "aspirant_documents",
    "branch_officials",
    "branches",
    "party_leaders",
    "party_values",
    "party_organs",
    "primary_results",
    "party_messages",
    "campaign_sharing",
    "recruitment_codes",
    "party_requests",
    "party_roles",
    "aspirants",
    "nomination_seats",
    "nomination_windows",
]
RENAMED = {"party_posts": "posts", "party_documents": "documents", "party_videos": "videos"}
# Constraint names a table rename keeps on Postgres; SQLite has no way to rename them.
RENAMED_CONSTRAINTS = [
    ("posts", "pk_party_posts", "pk_posts"),
    ("posts", "ck_party_posts_event_has_date", "ck_posts_event_has_date"),
    ("posts", "fk_party_posts_county_id_counties", "fk_posts_county_id_counties"),
    ("documents", "pk_party_documents", "pk_documents"),
    ("documents", "fk_party_documents_file_id_stored_files", "fk_documents_file_id_stored_files"),
    ("videos", "pk_party_videos", "pk_videos"),
]
POST_INDEXES = {
    "kind_published_event_date": ["kind", "published", "event_date"],
    "kind_published_published_on": ["kind", "published", "published_on"],
}
FILE_AREAS = ["site", "slides", "documents", "candidates"]
PARTY_FILE_AREAS = [
    "site",
    "slides",
    "leaders",
    "documents",
    "candidates",
    "minutes",
    "nominations",
]
SEAT_MATCHES_SCOPE = (
    "(seat = 'mca' AND office_level = 'ward') "
    "OR (seat = 'mp' AND office_level = 'constituency') "
    "OR (seat IN ('governor', 'senator', 'women_rep') AND office_level = 'county')"
)
PARTY_SEAT_MATCHES_SCOPE = (
    "(kind = 'party' AND seat IS NULL AND office_level = 'national') OR (kind <> 'party' AND "
    "seat IS NOT NULL AND ((seat = 'mca' AND office_level = 'ward') OR (seat = 'mp' AND "
    "office_level = 'constituency') OR (seat IN ('governor', 'senator', 'women_rep') AND "
    "office_level = 'county')))"
)


def _postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _enum_check(table: str, enum: str) -> str:
    """The name an enum's CHECK carries: prefixed when Alembic runs with the models' naming
    convention, as the app's own migrations do, and bare otherwise."""
    target = op.get_context().opts.get("target_metadata")
    named = getattr(target, "naming_convention", {}).get("ck")
    return op.f(f"ck_{table}_{enum}" if named else enum)


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _rename_tables(names: dict[str, str], constraints: list[tuple[str, str, str]]) -> None:
    for old, new in names.items():
        op.rename_table(old, new)
    if _postgres():
        posts = "posts" if "party_posts" in names else "party_posts"
        before = next(old for old, new in names.items() if new == posts)
        for enum in ("post_kind", "post_label"):
            old, new = _enum_check(before, enum), _enum_check(posts, enum)
            if old != new:
                constraints = [*constraints, (posts, old, new)]
        for table, old, new in constraints:
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")


def _post_indexes(table: str, old_prefix: str, new_prefix: str) -> None:
    for suffix, columns in POST_INDEXES.items():
        op.drop_index(f"ix_{old_prefix}_{suffix}", table_name=table)
        op.create_index(f"ix_{new_prefix}_{suffix}", table, columns, unique=False)


def upgrade() -> None:
    op.execute("DELETE FROM data_requests WHERE campaign_id IS NULL")
    op.execute("DELETE FROM volunteer_profiles WHERE campaign_id IS NULL")
    op.execute("DELETE FROM payments_in WHERE purpose = 'nomination_fee' OR campaign_id IS NULL")
    op.execute("DELETE FROM campaigns WHERE seat IS NULL")
    op.execute("DELETE FROM users WHERE role IS NULL AND NOT is_superuser")

    with op.batch_alter_table("candidate_profiles") as batch:
        batch.drop_constraint("uq_candidate_profiles_aspirant_id", type_="unique")
        batch.drop_constraint("fk_candidate_profiles_aspirant_id_aspirants", type_="foreignkey")
        batch.drop_column("aspirant_id")
    op.drop_index("ix_payments_in_aspirant_id", table_name="payments_in")
    with op.batch_alter_table("payments_in") as batch:
        batch.drop_constraint("fk_payments_in_aspirant_id_aspirants", type_="foreignkey")
        batch.drop_constraint(_enum_check("payments_in", "pay_in_purpose"), type_="check")
        batch.drop_column("aspirant_id")
        batch.drop_column("purpose")
    op.drop_index("ix_sms_log_party_message_id", table_name="sms_log")
    with op.batch_alter_table("sms_log") as batch:
        batch.drop_constraint("fk_sms_log_party_message_id_party_messages", type_="foreignkey")
        batch.drop_column("party_message_id")
    for table in PARTY_TABLES:
        op.drop_table(table)
    # After the drops: aspirant_documents restricts deleting the files it points at.
    op.execute(f"DELETE FROM stored_files WHERE NOT {_in('area', FILE_AREAS)}")

    op.drop_index("uq_volunteer_profiles_party_phone", table_name="volunteer_profiles")
    with op.batch_alter_table("volunteer_profiles") as batch:
        batch.drop_constraint("uq_volunteer_profiles_member_id", type_="unique")
        batch.drop_constraint(op.f("ck_volunteer_profiles_owner"), type_="check")
        batch.drop_constraint("fk_volunteer_profiles_member_id_party_members", type_="foreignkey")
        batch.drop_column("member_id")
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=False)

    op.drop_index("uq_users_member_login", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_party_member_id_party_members", type_="foreignkey")
        batch.drop_constraint("uq_users_id_kind", type_="unique")
        batch.drop_constraint(op.f("ck_users_kind_matches_role"), type_="check")
        batch.drop_constraint(_enum_check("users", "user_kind"), type_="check")
        batch.drop_column("party_member_id")
        batch.drop_column("kind")
    op.drop_table("party_members")
    op.drop_table("party_settings")

    with op.batch_alter_table("site_settings") as batch:
        batch.drop_constraint(_enum_check("site_settings", "organisation_type"), type_="check")
        batch.drop_column("organisation_type")

    op.drop_index("uq_campaigns_one_party_one_standalone", table_name="campaigns")
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint(op.f("ck_campaigns_seat_matches_scope"), type_="check")
        batch.drop_constraint(_enum_check("campaigns", "workspace_kind"), type_="check")
        batch.drop_column("kind")
        batch.alter_column("seat", existing_type=sa.String(20), nullable=False)
        batch.create_check_constraint(op.f("ck_campaigns_seat_matches_scope"), SEAT_MATCHES_SCOPE)

    with op.batch_alter_table("data_requests") as batch:
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=False)

    with op.batch_alter_table("stored_files") as batch:
        batch.drop_constraint(_enum_check("stored_files", "file_area"), type_="check")
        batch.create_check_constraint(
            _enum_check("stored_files", "file_area"), _in("area", FILE_AREAS)
        )

    _rename_tables(RENAMED, RENAMED_CONSTRAINTS)
    _post_indexes("posts", "party_posts", "posts")


def downgrade() -> None:
    _post_indexes("posts", "posts", "party_posts")
    back = {new: old for old, new in RENAMED.items()}
    _rename_tables(back, [(back[table], new, old) for table, old, new in RENAMED_CONSTRAINTS])
    with op.batch_alter_table("stored_files") as batch:
        batch.drop_constraint(_enum_check("stored_files", "file_area"), type_="check")
        batch.create_check_constraint(
            _enum_check("stored_files", "file_area"), _in("area", PARTY_FILE_AREAS)
        )

    with op.batch_alter_table("data_requests") as batch:
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=True)

    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint(op.f("ck_campaigns_seat_matches_scope"), type_="check")
        batch.add_column(sa.Column("kind", sa.String(20), nullable=True))
        batch.alter_column("seat", existing_type=sa.String(20), nullable=True)
    op.execute("UPDATE campaigns SET kind = 'standalone'")
    with op.batch_alter_table("campaigns") as batch:
        batch.alter_column("kind", existing_type=sa.String(20), nullable=False)
        batch.create_check_constraint(
            _enum_check("campaigns", "workspace_kind"),
            _in("kind", ["party", "hosted", "standalone"]),
        )
        batch.create_check_constraint(
            op.f("ck_campaigns_seat_matches_scope"), PARTY_SEAT_MATCHES_SCOPE
        )
    op.create_index(
        "uq_campaigns_one_party_one_standalone",
        "campaigns",
        ["kind"],
        unique=True,
        postgresql_where=sa.text("kind <> 'hosted'"),
        sqlite_where=sa.text("kind <> 'hosted'"),
    )

    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(sa.Column("organisation_type", sa.String(20), nullable=True))
    op.execute("UPDATE site_settings SET organisation_type = 'aspirant'")
    with op.batch_alter_table("site_settings") as batch:
        batch.alter_column("organisation_type", existing_type=sa.String(20), nullable=False)
        batch.create_check_constraint(
            _enum_check("site_settings", "organisation_type"),
            _in("organisation_type", ["party", "aspirant"]),
        )

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("kind", sa.String(8), nullable=True))
    op.execute("UPDATE users SET kind = CASE WHEN role IS NULL THEN 'staff' ELSE 'campaign' END")
    with op.batch_alter_table("users") as batch:
        batch.alter_column("kind", existing_type=sa.String(8), nullable=False)
        batch.create_check_constraint(
            _enum_check("users", "user_kind"), _in("kind", ["campaign", "staff", "member"])
        )
        batch.create_check_constraint(
            op.f("ck_users_kind_matches_role"), "(kind = 'campaign') = (role IS NOT NULL)"
        )
        batch.create_unique_constraint("uq_users_id_kind", ["id", "kind"])

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
    op.execute("INSERT INTO party_settings (id) VALUES (1)")

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("party_member_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_users_party_member_id_party_members",
            "party_members",
            ["party_member_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "uq_users_member_login",
        "users",
        ["party_member_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'member'"),
        sqlite_where=sa.text("kind = 'member'"),
    )

    with op.batch_alter_table("volunteer_profiles") as batch:
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=True)
        batch.add_column(sa.Column("member_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_volunteer_profiles_member_id_party_members",
            "party_members",
            ["member_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_unique_constraint("uq_volunteer_profiles_member_id", ["member_id"])
        batch.create_check_constraint(
            op.f("ck_volunteer_profiles_owner"), "(campaign_id IS NULL) = (member_id IS NOT NULL)"
        )
    op.create_index(
        "uq_volunteer_profiles_party_phone",
        "volunteer_profiles",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NULL"),
        sqlite_where=sa.text("campaign_id IS NULL"),
    )

    with op.batch_alter_table("sms_log") as batch:
        batch.add_column(sa.Column("party_message_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_sms_log_party_message_id_party_messages",
            "party_messages",
            ["party_message_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_sms_log_party_message_id", "sms_log", ["party_message_id"], unique=False)

    with op.batch_alter_table("payments_in") as batch:
        batch.add_column(sa.Column("purpose", sa.String(20), nullable=True))
        batch.add_column(sa.Column("aspirant_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_payments_in_aspirant_id_aspirants",
            "aspirants",
            ["aspirant_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute("UPDATE payments_in SET purpose = 'contribution'")
    with op.batch_alter_table("payments_in") as batch:
        batch.alter_column("purpose", existing_type=sa.String(20), nullable=False)
        batch.create_check_constraint(
            _enum_check("payments_in", "pay_in_purpose"),
            _in("purpose", ["nomination_fee", "contribution"]),
        )
    op.create_index("ix_payments_in_aspirant_id", "payments_in", ["aspirant_id"], unique=False)

    with op.batch_alter_table("candidate_profiles") as batch:
        batch.add_column(sa.Column("aspirant_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_candidate_profiles_aspirant_id_aspirants",
            "aspirants",
            ["aspirant_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_unique_constraint("uq_candidate_profiles_aspirant_id", ["aspirant_id"])

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
