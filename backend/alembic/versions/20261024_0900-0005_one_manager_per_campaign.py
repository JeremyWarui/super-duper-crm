"""A campaign has at most one manager.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-24 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_campaign_members_one_manager",
        "campaign_members",
        ["campaign_id"],
        unique=True,
        postgresql_where=sa.text("role = 'manager'"),
        sqlite_where=sa.text("role = 'manager'"),
    )


def downgrade() -> None:
    op.drop_index("uq_campaign_members_one_manager", table_name="campaign_members")
