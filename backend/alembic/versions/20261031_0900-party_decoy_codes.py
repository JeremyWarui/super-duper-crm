"""Withdrawal codes handed to numbers already on the party register.

Revision ID: party_decoy_codes
Revises: party_members
Create Date: 2026-10-31 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "party_decoy_codes"
down_revision: str | None = "party_members"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "party_decoy_codes",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_party_decoy_codes")),
    )


def downgrade() -> None:
    op.drop_table("party_decoy_codes")
