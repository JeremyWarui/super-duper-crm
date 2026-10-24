"""A sign-up link per campaign, and a private withdrawal code per self-signed supporter.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-25 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("signup_code", sa.String(length=24), nullable=True))
        batch.add_column(
            sa.Column("signups_open", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    # One statement, so the migration also renders offline as SQL.
    if op.get_context().dialect.name == "sqlite":
        op.execute("UPDATE campaigns SET signup_code = lower(hex(randomblob(9)))")
    else:
        op.execute(
            "UPDATE campaigns SET signup_code = substr(md5(random()::text || id::text), 1, 18)"
        )
    with op.batch_alter_table("campaigns") as batch:
        batch.alter_column("signup_code", existing_type=sa.String(length=24), nullable=False)
        batch.alter_column("signups_open", existing_type=sa.Boolean(), server_default=None)
        batch.create_unique_constraint(op.f("uq_campaigns_signup_code"), ["signup_code"])

    with op.batch_alter_table("supporters") as batch:
        batch.add_column(sa.Column("withdraw_code", sa.String(length=32), nullable=True))
        batch.create_unique_constraint(op.f("uq_supporters_withdraw_code"), ["withdraw_code"])


def downgrade() -> None:
    with op.batch_alter_table("supporters") as batch:
        batch.drop_constraint(op.f("uq_supporters_withdraw_code"), type_="unique")
        batch.drop_column("withdraw_code")
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint(op.f("uq_campaigns_signup_code"), type_="unique")
        batch.drop_column("signups_open")
        batch.drop_column("signup_code")
