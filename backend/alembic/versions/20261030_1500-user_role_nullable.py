"""A login may have no campaign role.

Revision ID: user_role_nullable
Revises: consent_on_supporters
Create Date: 2026-10-30 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "user_role_nullable"
down_revision: str | None = "consent_on_supporters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE = sa.String(length=20)


def _refuse_roleless_users() -> None:
    if op.get_context().as_sql:
        return
    rows = (
        op.get_bind().execute(sa.text("SELECT id FROM users WHERE role IS NULL ORDER BY id")).all()
    )
    if rows:
        ids = ", ".join(str(row[0]) for row in rows)
        raise RuntimeError(f"{len(rows)} users have no role and would break NOT NULL: {ids}")


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=ROLE, nullable=True)


def downgrade() -> None:
    _refuse_roleless_users()
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=ROLE, nullable=False)
