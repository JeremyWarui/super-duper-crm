"""Make campaign_members name each campaign's candidate once, before the column goes.

A campaign whose candidate login has no row yet gets one. A campaign that then
has no candidate row, several, or one for somebody other than
`campaigns.candidate_id` stops the upgrade and is named: which person a
campaign is for is a person's decision.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-13 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_ID = {
    "postgresql": "gen_random_uuid()",
    "cockroachdb": "gen_random_uuid()",
    # SQLite keeps a uuid as 32 hex characters, the same shape SQLAlchemy writes.
    "sqlite": "lower(hex(randomblob(16)))",
}

_CHECK = """
    SELECT c.title,
           (SELECT COUNT(*) FROM campaign_members m
             WHERE m.campaign_id = c.id AND m.role = 'candidate') AS candidates,
           (SELECT COUNT(*) FROM campaign_members m
             WHERE m.campaign_id = c.id AND m.role = 'candidate'
               AND m.user_id = c.candidate_id) AS matching
    FROM campaigns c
    ORDER BY c.title
"""


def _new_id() -> str:
    name = op.get_bind().dialect.name
    if name not in _NEW_ID:
        raise RuntimeError(f"No uuid generator known for {name}; add one before migrating.")
    return _NEW_ID[name]


def upgrade() -> None:
    new_id = _new_id()
    op.execute(
        sa.text(
            f"""
            INSERT INTO campaign_members (id, campaign_id, user_id, role, created_at)
            SELECT {new_id}, c.id, u.id, u.role, CURRENT_TIMESTAMP
            FROM campaigns c
            JOIN users u ON u.id = c.candidate_id
            WHERE u.role = 'candidate'
              AND NOT EXISTS (
                SELECT 1 FROM campaign_members m
                WHERE m.campaign_id = c.id AND m.user_id = u.id
            )
            """
        )
    )

    # Rendered as SQL there is no database, so there are no rows to check.
    if op.get_context().as_sql:
        return
    wrong = [
        f"{title} ({candidates} candidate rows, {matching} for campaigns.candidate_id)"
        for title, candidates, matching in op.get_bind().execute(sa.text(_CHECK))
        if candidates != 1 or matching != 1
    ]
    if wrong:
        raise RuntimeError(
            "These campaigns do not name exactly one candidate in campaign_members, so "
            "campaigns.candidate_id cannot be dropped yet: " + "; ".join(wrong)
        )


def downgrade() -> None:
    """Leave the rows; the next revision's downgrade reads the column back from them."""
