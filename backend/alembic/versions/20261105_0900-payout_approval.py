"""A party payment waits for the party super admin's approval before it goes out.

Revision ID: payout_approval
Revises: party_payments
Create Date: 2026-11-05 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "payout_approval"
down_revision: str | None = "party_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("party_payments") as batch:
        batch.add_column(sa.Column("approved_by_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("approved_by_name", sa.String(150), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            op.f("fk_party_payments_approved_by_id_users"),
            "users",
            ["approved_by_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("party_payments") as batch:
        batch.drop_constraint(op.f("fk_party_payments_approved_by_id_users"), type_="foreignkey")
        batch.drop_column("approved_at")
        batch.drop_column("approved_by_name")
        batch.drop_column("approved_by_id")
