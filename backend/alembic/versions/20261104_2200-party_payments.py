"""Payments the party makes to agents, volunteers, members and staff.

Revision ID: party_payments
Revises: candidate_profiles
Create Date: 2026-11-04 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "party_payments"
down_revision: str | None = "candidate_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "party_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "payee_kind",
            sa.Enum(
                "polling_agent",
                "party_agent",
                "volunteer",
                "member",
                "staff",
                name="payee_kind",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("volunteer_id", sa.Uuid(), nullable=True),
        sa.Column("registration_centre_id", sa.Uuid(), nullable=True),
        sa.Column("polling_station", sa.String(200), nullable=False, server_default=""),
        sa.Column("aspirant_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_label", sa.String(200), nullable=False, server_default=""),
        sa.Column("purpose", sa.String(150), nullable=False, server_default=""),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_name", sa.String(150), nullable=False),
        sa.Column("recipient_phone", sa.String(20), nullable=False, server_default=""),
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
        sa.Column("reference", sa.String(50), nullable=False, server_default=""),
        sa.Column("provider", sa.String(20), nullable=False, server_default=""),
        sa.Column("failure_reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sending_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount_kes > 0", name=op.f("ck_party_payments_amount_kes_positive")),
        sa.CheckConstraint(
            "member_id IS NULL OR volunteer_id IS NULL", name=op.f("ck_party_payments_one_register")
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["party_members.id"],
            name=op.f("fk_party_payments_member_id_party_members"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["volunteer_id"],
            ["volunteer_profiles.id"],
            name=op.f("fk_party_payments_volunteer_id_volunteer_profiles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registration_centre_id"],
            ["registration_centres.id"],
            name=op.f("fk_party_payments_registration_centre_id_registration_centres"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["aspirant_id"],
            ["aspirants.id"],
            name=op.f("fk_party_payments_aspirant_id_aspirants"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_party_payments_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_payments")),
    )
    op.create_index(op.f("ix_party_payments_member_id"), "party_payments", ["member_id"])
    op.create_index(op.f("ix_party_payments_volunteer_id"), "party_payments", ["volunteer_id"])
    op.create_index(op.f("ix_party_payments_aspirant_id"), "party_payments", ["aspirant_id"])
    op.create_index(op.f("ix_party_payments_reference"), "party_payments", ["reference"])


def downgrade() -> None:
    op.drop_table("party_payments")
