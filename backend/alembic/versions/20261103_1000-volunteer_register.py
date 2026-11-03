"""Volunteer register: a volunteer carries their own details and may belong to a campaign.

Revision ID: volunteer_register
Revises: public_content
Create Date: 2026-11-03 10:00:00.000000

Each existing profile takes its member's name, phone, email and ward. Downgrading deletes
volunteers with no member.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "volunteer_register"
down_revision: str | None = "public_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARTY_PHONE = "campaign_id IS NULL"
PROFESSION_CHECK = "ck_volunteer_profiles_profession"
REQUIRED = ("first_name", "last_name", "phone", "ward_id")


def upgrade() -> None:
    with op.batch_alter_table("volunteer_profiles") as batch:
        batch.add_column(sa.Column("campaign_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("first_name", sa.String(75), nullable=True))
        batch.add_column(sa.Column("last_name", sa.String(75), nullable=True))
        batch.add_column(sa.Column("phone", sa.String(20), nullable=True))
        batch.add_column(sa.Column("email", sa.String(254), nullable=True))
        batch.add_column(sa.Column("ward_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("registration_centre_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("profession", sa.String(20), nullable=True))
        batch.create_check_constraint(
            op.f(PROFESSION_CHECK),
            "profession IN ('farmer', 'teacher', 'business', 'student', 'other')",
        )
        batch.add_column(
            sa.Column("profession_other", sa.String(100), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("interest_other", sa.String(100), nullable=False, server_default="")
        )

    position = "strpos" if op.get_context().dialect.name == "postgresql" else "instr"
    name = "trim(m.full_name)"
    gap = f"{position}({name}, ' ')"
    first = f"CASE WHEN {gap} > 0 THEN substr({name}, 1, {gap} - 1) ELSE {name} END"
    last = f"CASE WHEN {gap} > 0 THEN trim(substr({name}, {gap} + 1)) ELSE '' END"

    def member(value: str) -> str:
        return f"(SELECT {value} FROM party_members m WHERE m.id = volunteer_profiles.member_id)"

    op.execute(
        "UPDATE volunteer_profiles SET "
        f"first_name = {member(f'substr({first}, 1, 75)')}, "
        f"last_name = {member(f'substr({last}, 1, 75)')}, "
        f"phone = {member('m.phone')}, "
        f"email = {member('m.email')}, "
        f"ward_id = {member('m.ward_id')}"
    )

    with op.batch_alter_table("volunteer_profiles") as batch:
        batch.alter_column("member_id", existing_type=sa.Uuid(), nullable=True)
        for name, kind in zip(
            REQUIRED, (sa.String(75), sa.String(75), sa.String(20), sa.Uuid()), strict=True
        ):
            batch.alter_column(name, existing_type=kind, nullable=False)
        batch.alter_column("profession_other", server_default=None)
        batch.alter_column("interest_other", server_default=None)
        batch.create_foreign_key(
            op.f("fk_volunteer_profiles_campaign_id_campaigns"),
            "campaigns",
            ["campaign_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            op.f("fk_volunteer_profiles_ward_id_wards"),
            "wards",
            ["ward_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            op.f("fk_volunteer_profiles_registration_centre_id_registration_centres"),
            "registration_centres",
            ["registration_centre_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_unique_constraint(
            "uq_volunteer_profiles_campaign_phone", ["campaign_id", "phone"]
        )
    op.create_index(
        "uq_volunteer_profiles_party_phone",
        "volunteer_profiles",
        ["phone"],
        unique=True,
        sqlite_where=sa.text(PARTY_PHONE),
        postgresql_where=sa.text(PARTY_PHONE),
    )
    op.create_index(
        "ix_volunteer_profiles_campaign_id_status",
        "volunteer_profiles",
        ["campaign_id", "status"],
    )
    op.create_index(op.f("ix_volunteer_profiles_ward_id"), "volunteer_profiles", ["ward_id"])


def downgrade() -> None:
    op.execute("DELETE FROM volunteer_profiles WHERE member_id IS NULL")
    op.drop_index(op.f("ix_volunteer_profiles_ward_id"), table_name="volunteer_profiles")
    op.drop_index("ix_volunteer_profiles_campaign_id_status", table_name="volunteer_profiles")
    op.drop_index("uq_volunteer_profiles_party_phone", table_name="volunteer_profiles")
    with op.batch_alter_table("volunteer_profiles") as batch:
        batch.drop_constraint("uq_volunteer_profiles_campaign_phone", type_="unique")
        batch.drop_constraint(
            op.f("fk_volunteer_profiles_registration_centre_id_registration_centres"),
            type_="foreignkey",
        )
        batch.drop_constraint(op.f(PROFESSION_CHECK), type_="check")
        batch.drop_constraint(op.f("fk_volunteer_profiles_ward_id_wards"), type_="foreignkey")
        batch.drop_constraint(
            op.f("fk_volunteer_profiles_campaign_id_campaigns"), type_="foreignkey"
        )
        for name in (
            "interest_other",
            "profession_other",
            "profession",
            "registration_centre_id",
            "ward_id",
            "email",
            "phone",
            "last_name",
            "first_name",
            "campaign_id",
        ):
            batch.drop_column(name)
        batch.alter_column("member_id", existing_type=sa.Uuid(), nullable=False)
