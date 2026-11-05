"""Campaign roles coordinator, comms and agent; pending logins; coordinator areas.

Revision ID: campaign_roles
Revises: candidate_profiles_by_campaign
Create Date: 2026-11-05 14:00:00.000000

Downgrade refuses while a login holds one of the new roles.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "campaign_roles"
down_revision: str | None = "candidate_profiles_by_campaign"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ROLES = ("candidate", "manager", "mobilizer")
NEW_ROLES = ("coordinator", "comms", "agent")
# The role CHECK on each table, by the name `alembic upgrade` gives it.
ROLE_CHECKS = {"users": "ck_users_user_role", "campaign_members": "ck_campaign_members_member_role"}


def _set_roles(table: str, roles: Sequence[str]) -> None:
    """Replace the CHECK listing the roles this table's role column allows.

    The old CHECK is looked up, as its name depends on how the table was first migrated.
    """
    name = ROLE_CHECKS[table]
    if op.get_context().as_sql:
        olds = [name]
    else:
        olds = [
            check["name"]
            for check in sa.inspect(op.get_bind()).get_check_constraints(table)
            if "role" in check["sqltext"] and "kind" not in check["sqltext"]
        ]
    allowed = "role IN (" + ", ".join(f"'{role}'" for role in roles) + ")"
    with op.batch_alter_table(table) as batch:
        for old in olds:
            batch.drop_constraint(op.f(old), type_="check")
        batch.create_check_constraint(op.f(name), allowed)


def upgrade() -> None:
    for table in ROLE_CHECKS:
        _set_roles(table, OLD_ROLES[:2] + NEW_ROLES[:2] + OLD_ROLES[2:] + NEW_ROLES[2:])
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.create_check_constraint(
            op.f("ck_users_pending_is_inactive"), "NOT (pending AND is_active)"
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
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_campaign_member_areas_ward_id_wards"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_campaign_member_areas_registration_centre_id_registration_centres"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_member_areas")),
        sa.UniqueConstraint(
            "campaign_member_id",
            "ward_id",
            name=op.f("uq_campaign_member_areas_campaign_member_id_ward_id"),
        ),
        sa.UniqueConstraint(
            "campaign_member_id",
            "registration_centre_id",
            name=op.f("uq_campaign_member_areas_campaign_member_id_registration_centre_id"),
        ),
    )
    op.create_index(
        op.f("ix_campaign_member_areas_campaign_member_id"),
        "campaign_member_areas",
        ["campaign_member_id"],
    )


def downgrade() -> None:
    roles = ", ".join(f"'{role}'" for role in NEW_ROLES)
    if not op.get_context().as_sql and op.get_bind().scalar(
        sa.text(f"SELECT count(*) FROM users WHERE role IN ({roles})")
    ):
        raise RuntimeError("A login holds a coordinator, comms or agent role; remove it first.")
    op.drop_index(
        op.f("ix_campaign_member_areas_campaign_member_id"), table_name="campaign_member_areas"
    )
    op.drop_table("campaign_member_areas")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint(op.f("ck_users_pending_is_inactive"), type_="check")
        batch.drop_column("pending")
    for table in ROLE_CHECKS:
        _set_roles(table, OLD_ROLES)
