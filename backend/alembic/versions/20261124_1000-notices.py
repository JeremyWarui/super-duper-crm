"""Notices: a note to one login, such as a target that changed with the team's scenario.

Revision ID: notices
Revises: invite_runs
Create Date: 2026-11-24 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "notices"
down_revision: str | None = "invite_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("url", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_notices_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notices")),
    )
    op.create_index(op.f("ix_notices_campaign_id"), "notices", ["campaign_id"])
    op.create_index(op.f("ix_notices_user_id"), "notices", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_notices_user_id"), table_name="notices")
    op.drop_index(op.f("ix_notices_campaign_id"), table_name="notices")
    op.drop_table("notices")
