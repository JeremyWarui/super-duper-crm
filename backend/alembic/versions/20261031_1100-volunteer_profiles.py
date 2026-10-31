"""Volunteer profiles, and the volunteer withdrawal request.

Revision ID: volunteer_profiles
Revises: party_requests
Create Date: 2026-10-31 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "volunteer_profiles"
down_revision: str | None = "party_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KIND_CHECK = "ck_party_requests_party_request_kind"


def upgrade() -> None:
    op.create_table(
        "volunteer_profiles",
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("availability_notes", sa.Text(), nullable=True),
        sa.Column("preferred_contact", sa.String(length=20), nullable=False),
        sa.Column("consent_wording", sa.Text(), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdraw_code", sa.String(length=32), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "consent_wording <> ''", name=op.f("ck_volunteer_profiles_consent_wording_not_empty")
        ),
        sa.CheckConstraint(
            "status IN ('interested', 'active', 'inactive', 'withdrawn')",
            name=op.f("ck_volunteer_profiles_volunteer_status"),
        ),
        sa.CheckConstraint(
            "preferred_contact IN ('call', 'sms', 'whatsapp', 'email')",
            name=op.f("ck_volunteer_profiles_contact_method"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["party_members.id"],
            name=op.f("fk_volunteer_profiles_member_id_party_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_volunteer_profiles")),
        sa.UniqueConstraint("member_id", name="uq_volunteer_profiles_member_id"),
        sa.UniqueConstraint("withdraw_code", name=op.f("uq_volunteer_profiles_withdraw_code")),
    )
    with op.batch_alter_table("party_requests") as batch:
        batch.drop_constraint(op.f(KIND_CHECK), type_="check")
        batch.create_check_constraint(
            op.f(KIND_CHECK), "kind IN ('join', 'withdraw', 'volunteer_withdraw')"
        )


def downgrade() -> None:
    op.execute("DELETE FROM party_requests WHERE kind = 'volunteer_withdraw'")
    with op.batch_alter_table("party_requests") as batch:
        batch.drop_constraint(op.f(KIND_CHECK), type_="check")
        batch.create_check_constraint(op.f(KIND_CHECK), "kind IN ('join', 'withdraw')")
    op.drop_table("volunteer_profiles")
