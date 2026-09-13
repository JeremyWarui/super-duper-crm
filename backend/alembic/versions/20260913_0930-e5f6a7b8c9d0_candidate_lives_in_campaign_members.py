"""Drop campaigns.candidate_id: a campaign's candidate lives in campaign_members alone.

A partial unique index allows one candidate row per campaign.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-13 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ONE_CANDIDATE = "uq_campaign_members_one_candidate"


def _only_candidates() -> sa.TextClause:
    return sa.text("role = 'candidate'")


def upgrade() -> None:
    with op.batch_alter_table("campaigns") as batch:
        # The key goes before its index: CockroachDB refuses to drop an index a key uses.
        batch.drop_constraint("fk_campaigns_candidate_id_users", type_="foreignkey")
        batch.drop_index("ix_campaigns_candidate_id")
        batch.drop_column("candidate_id")
    op.create_index(
        ONE_CANDIDATE,
        "campaign_members",
        ["campaign_id"],
        unique=True,
        postgresql_where=_only_candidates(),
        sqlite_where=_only_candidates(),
    )


def downgrade() -> None:
    op.drop_index(ONE_CANDIDATE, table_name="campaign_members")
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("candidate_id", sa.Uuid(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE campaigns SET candidate_id = (
                SELECT m.user_id FROM campaign_members m
                WHERE m.campaign_id = campaigns.id AND m.role = 'candidate'
            )
            """
        )
    )
    with op.batch_alter_table("campaigns") as batch:
        batch.alter_column("candidate_id", existing_type=sa.Uuid(), nullable=False)
        batch.create_foreign_key(
            "fk_campaigns_candidate_id_users",
            "users",
            ["candidate_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_campaigns_candidate_id", ["candidate_id"], unique=False)
