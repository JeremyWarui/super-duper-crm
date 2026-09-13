"""Put the people an existing deployment already has onto their campaigns.

Every campaign's candidate comes from `campaigns.candidate_id`, and everybody
with a ground row from `mobilizers.user_id`. Both take the role from the login
itself, because the route that wrote those ground rows accepted any user: a
manager's login on one would otherwise arrive here calling itself a mobilizer,
which is the disagreement this table exists to end.

Managers had no link to a campaign before `campaign_members` existed, so there
are none to move; they are put on with `campaign-crm add-member`.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-12 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Postgres and CockroachDB spell a new uuid differently from SQLite, which has
# no generator at all, so the id is built from random bytes everywhere.
_NEW_ID = {
    "postgresql": "gen_random_uuid()",
    "cockroachdb": "gen_random_uuid()",
    # SQLite keeps a uuid as 32 hex characters, the same shape SQLAlchemy writes.
    "sqlite": "lower(hex(randomblob(16)))",
}


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
            WHERE NOT EXISTS (
                SELECT 1 FROM campaign_members m
                WHERE m.campaign_id = c.id AND m.user_id = u.id
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO campaign_members (id, campaign_id, user_id, role, created_at)
            SELECT {new_id}, b.campaign_id, u.id, u.role, CURRENT_TIMESTAMP
            FROM mobilizers b
            JOIN users u ON u.id = b.user_id
            WHERE NOT EXISTS (
                SELECT 1 FROM campaign_members m
                WHERE m.campaign_id = b.campaign_id AND m.user_id = u.id
            )
            """
        )
    )


def downgrade() -> None:
    """Leave the rows. Deleting them would take memberships added since."""
