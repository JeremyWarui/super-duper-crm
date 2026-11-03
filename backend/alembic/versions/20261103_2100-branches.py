"""County branches: one per county, with its officials, office and next meeting.

Revision ID: branches
Revises: subscribers
Create Date: 2026-11-03 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "branches"
down_revision: str | None = "subscribers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("county_id", sa.Uuid(), nullable=False),
        sa.Column("chairperson", sa.String(150), nullable=False, server_default=""),
        sa.Column("secretary", sa.String(150), nullable=False, server_default=""),
        sa.Column("office_address", sa.String(300), nullable=False, server_default=""),
        sa.Column("phone", sa.String(20), nullable=False, server_default=""),
        sa.Column("email", sa.String(254), nullable=False, server_default=""),
        sa.Column("next_meeting_on", sa.Date(), nullable=True),
        sa.Column("next_meeting_venue", sa.String(150), nullable=False, server_default=""),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["county_id"],
            ["counties.id"],
            name=op.f("fk_branches_county_id_counties"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branches")),
        sa.UniqueConstraint("county_id", name=op.f("uq_branches_county_id")),
    )


def downgrade() -> None:
    op.drop_table("branches")
