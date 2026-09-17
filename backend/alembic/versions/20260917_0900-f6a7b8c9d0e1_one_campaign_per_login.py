"""Hold every login to one campaign.

A unique index on campaign_members.user_id. A login already on more than one
campaign stops the upgrade and is named with its campaigns: which one it keeps
is a person's decision.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-17 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ONE_CAMPAIGN = "uq_campaign_members_one_campaign_per_user"

_ON_SEVERAL = """
    SELECT u.username, c.title
    FROM campaign_members m
    JOIN users u ON u.id = m.user_id
    JOIN campaigns c ON c.id = m.campaign_id
    WHERE m.user_id IN (
        SELECT user_id FROM campaign_members GROUP BY user_id HAVING COUNT(*) > 1
    )
    ORDER BY u.username, c.title
"""


def upgrade() -> None:
    # Rendered as SQL there is no database, so there are no rows to check.
    if not op.get_context().as_sql:
        several: dict[str, list[str]] = {}
        for username, title in op.get_bind().execute(sa.text(_ON_SEVERAL)):
            several.setdefault(username, []).append(title)
        if several:
            raise RuntimeError(
                "These logins are on more than one campaign. Take each off all but one "
                "(campaign-crm remove-member), then migrate again: "
                + "; ".join(f"{name} ({', '.join(titles)})" for name, titles in several.items())
            )
    op.create_index(ONE_CAMPAIGN, "campaign_members", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index(ONE_CAMPAIGN, table_name="campaign_members")
