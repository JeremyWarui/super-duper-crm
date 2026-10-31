"""Aspirants: a party member's nomination for a seat, and its campaign.

Revision ID: aspirants
Revises: staff_kind
Create Date: 2026-11-01 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "aspirants"
down_revision: str | None = "staff_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE_NOMINATION = "status IN ('draft', 'submitted', 'approved', 'suspended')"


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=20, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "aspirants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column(
            "seat", _enum("seat", "mca", "mp", "governor", "senator", "women_rep"), nullable=False
        ),
        sa.Column("county_id", sa.Uuid(), nullable=True),
        sa.Column("constituency_id", sa.Uuid(), nullable=True),
        sa.Column("ward_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            _enum(
                "aspirant_status",
                "draft",
                "submitted",
                "approved",
                "rejected",
                "withdrawn",
                "suspended",
            ),
            nullable=False,
        ),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(seat = 'mca' AND ward_id IS NOT NULL "
            "AND constituency_id IS NULL AND county_id IS NULL) "
            "OR (seat = 'mp' AND constituency_id IS NOT NULL "
            "AND ward_id IS NULL AND county_id IS NULL) "
            "OR (seat IN ('governor', 'senator', 'women_rep') AND county_id IS NOT NULL "
            "AND ward_id IS NULL AND constituency_id IS NULL)",
            name=op.f("ck_aspirants_area_matches_seat"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["party_members.id"],
            name=op.f("fk_aspirants_member_id_party_members"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_aspirants_county_id_counties"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["constituency_id"],
            ["constituencies.id"],
            name=op.f("fk_aspirants_constituency_id_constituencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ward_id"], ["wards.id"], name=op.f("fk_aspirants_ward_id_wards"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["users.id"],
            name=op.f("fk_aspirants_decided_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_aspirants_campaign_id_campaigns"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_aspirants_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aspirants")),
        sa.UniqueConstraint("campaign_id", name=op.f("uq_aspirants_campaign_id")),
    )
    op.create_index(op.f("ix_aspirants_member_id"), "aspirants", ["member_id"])
    op.create_index(op.f("ix_aspirants_seat"), "aspirants", ["seat"])
    op.create_index(op.f("ix_aspirants_status"), "aspirants", ["status"])
    op.create_index(
        "uq_aspirants_one_live_per_member",
        "aspirants",
        ["member_id"],
        unique=True,
        sqlite_where=sa.text(LIVE_NOMINATION),
        postgresql_where=sa.text(LIVE_NOMINATION),
    )


def downgrade() -> None:
    op.drop_table("aspirants")
