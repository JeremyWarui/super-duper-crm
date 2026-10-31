"""The party member register.

Revision ID: party_members
Revises: party_roles
Create Date: 2026-10-30 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "party_members"
down_revision: str | None = "party_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "party_members",
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
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
                length=20,
                create_constraint=True,
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
                length=20,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdraw_code", sa.String(length=32), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
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
            ["ward_id"],
            ["wards.id"],
            name=op.f("fk_party_members_ward_id_wards"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_members")),
        sa.UniqueConstraint("phone", name="uq_party_members_phone"),
        sa.UniqueConstraint("withdraw_code", name=op.f("uq_party_members_withdraw_code")),
    )
    op.create_index(op.f("ix_party_members_full_name"), "party_members", ["full_name"])
    op.create_index(op.f("ix_party_members_status"), "party_members", ["status"])
    op.create_index(op.f("ix_party_members_ward_id"), "party_members", ["ward_id"])


def downgrade() -> None:
    op.drop_table("party_members")
