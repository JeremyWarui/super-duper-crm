"""Team sign-up: registrations, polling agents, and each workspace's team link.

Revision ID: team_registrations_and_agents
Revises: login_links_and_email_log
Create Date: 2026-11-06 14:00:00.000000

Every existing workspace gets its own random team code.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "team_registrations_and_agents"
down_revision: str | None = "login_links_and_email_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STILL_COUNTS = "status != 'rejected'"


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("team_code", sa.String(24), nullable=True))
    # One statement, so it also renders for `alembic upgrade --sql`.
    if op.get_context().dialect.name == "postgresql":
        op.execute(
            "UPDATE campaigns SET team_code = substr(md5(random()::text || id::text), 1, 16)"
        )
    else:
        op.execute("UPDATE campaigns SET team_code = lower(hex(randomblob(8)))")
    with op.batch_alter_table("campaigns") as batch:
        batch.alter_column("team_code", existing_type=sa.String(24), nullable=False)
        batch.create_unique_constraint(op.f("uq_campaigns_team_code"), ["team_code"])

    op.create_table(
        "team_registrations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("first_name", sa.String(150), nullable=False),
        sa.Column("last_name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("id_number", sa.String(20), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("consent_wording", sa.Text(), nullable=False),
        sa.Column("consent_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "role IN ('mobilizer', 'agent')", name=op.f("ck_team_registrations_field_role")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name=op.f("ck_team_registrations_registration_status"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_team_registrations_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_team_registrations_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_team_registrations_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_team_registrations_ward_id_wards"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_team_registrations_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_registrations")),
        sa.UniqueConstraint("user_id", name=op.f("uq_team_registrations_user_id")),
    )
    op.create_index(
        op.f("ix_team_registrations_campaign_id"), "team_registrations", ["campaign_id"]
    )
    for column in ("phone", "id_number"):
        op.create_index(
            f"uq_team_registrations_campaign_{column}",
            "team_registrations",
            ["campaign_id", column],
            unique=True,
            postgresql_where=sa.text(STILL_COUNTS),
            sqlite_where=sa.text(STILL_COUNTS),
        )

    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("training_date", sa.Date(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "status IN ('applied', 'vetted', 'trained', 'ready')",
            name=op.f("ck_agents_agent_status"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_agents_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_agents_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_agents_ward_id_wards"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_agents_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents")),
        sa.UniqueConstraint("user_id", name=op.f("uq_agents_user_id")),
    )
    for column in ("campaign_id", "ward_id", "registration_centre_id"):
        op.create_index(op.f(f"ix_agents_{column}"), "agents", [column])


def downgrade() -> None:
    for column in ("campaign_id", "ward_id", "registration_centre_id"):
        op.drop_index(op.f(f"ix_agents_{column}"), table_name="agents")
    op.drop_table("agents")
    for column in ("phone", "id_number"):
        op.drop_index(f"uq_team_registrations_campaign_{column}", table_name="team_registrations")
    op.drop_index(op.f("ix_team_registrations_campaign_id"), table_name="team_registrations")
    op.drop_table("team_registrations")
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint(op.f("uq_campaigns_team_code"), type_="unique")
        batch.drop_column("team_code")
