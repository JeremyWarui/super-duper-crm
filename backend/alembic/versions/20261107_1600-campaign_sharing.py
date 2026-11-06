"""What a hosted campaign shares with the party.

Revision ID: campaign_sharing
Revises: nomination_windows
Create Date: 2026-11-07 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "campaign_sharing"
down_revision: str | None = "nomination_windows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("campaign_sharing")
