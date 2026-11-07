"""A party text can go to one constituency.

Revision ID: party_message_constituency
Revises: drop_two_step
Create Date: 2026-11-07 23:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "party_message_constituency"
down_revision: str | None = "drop_two_step"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("party_messages") as batch:
        batch.add_column(sa.Column("constituency_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_party_messages_constituency_id_constituencies"),
            "constituencies",
            ["constituency_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("party_messages") as batch:
        batch.drop_constraint(
            op.f("fk_party_messages_constituency_id_constituencies"), type_="foreignkey"
        )
        batch.drop_column("constituency_id")
