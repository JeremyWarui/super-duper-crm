"""Sign-in is email and password only: the one-time handoff Google sign-in used is gone.

Revision ID: drop_google_handoff
Revises: notice_history
Create Date: 2026-11-26 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "drop_google_handoff"
down_revision: str | None = "notice_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("auth_tokens") as batch:
        batch.drop_constraint("uq_auth_tokens_handoff_hash", type_="unique")
        batch.drop_column("handoff_expires_at")
        batch.drop_column("handoff_hash")


def downgrade() -> None:
    with op.batch_alter_table("auth_tokens") as batch:
        batch.add_column(sa.Column("handoff_hash", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("handoff_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_unique_constraint("uq_auth_tokens_handoff_hash", ["handoff_hash"])
