"""Who works on a campaign, and in what capacity.

Creates `campaign_members`. Nothing is altered and nothing is dropped, so
existing rows are untouched; every campaign starts with no members and its
people are put back with `campaign-crm assign-manager`.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-12 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
                "mobilizer",
                name="member_role",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_members_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_campaign_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_members")),
        sa.UniqueConstraint(
            "campaign_id", "user_id", name=op.f("uq_campaign_members_campaign_id_user_id")
        ),
    )
    op.create_index(
        op.f("ix_campaign_members_campaign_id"), "campaign_members", ["campaign_id"], unique=False
    )
    op.create_index(
        op.f("ix_campaign_members_user_id"), "campaign_members", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_campaign_members_user_id"), table_name="campaign_members")
    op.drop_index(op.f("ix_campaign_members_campaign_id"), table_name="campaign_members")
    op.drop_table("campaign_members")
