"""Public requests to the party register, applied out of band.

Revision ID: party_requests
Revises: party_decoy_codes
Create Date: 2026-10-31 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "party_requests"
down_revision: str | None = "party_decoy_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("party_decoy_codes")
    op.create_table(
        "party_requests",
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('join', 'withdraw')", name=op.f("ck_party_requests_party_request_kind")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_requests")),
    )
    op.create_index("ix_party_requests_created_at", "party_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_party_requests_created_at", table_name="party_requests")
    op.drop_table("party_requests")
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
