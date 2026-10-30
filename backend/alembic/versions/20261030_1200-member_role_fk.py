"""A campaign member's role is held equal to its login's role by the database.

Revision ID: member_role_fk
Revises: schema_20261024
Create Date: 2026-10-30 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "member_role_fk"
down_revision: str | None = "schema_20261024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _refuse_mismatched_roles() -> None:
    if op.get_context().as_sql:
        return
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT m.id FROM campaign_members m JOIN users u ON u.id = m.user_id "
                "WHERE m.role <> u.role ORDER BY m.id"
            )
        )
        .all()
    )
    if rows:
        ids = ", ".join(str(row[0]) for row in rows)
        raise RuntimeError(
            f"campaign_members rows whose role differs from their user's role: {ids}"
        )


def upgrade() -> None:
    _refuse_mismatched_roles()
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint(op.f("uq_users_id_role"), ["id", "role"])
    with op.batch_alter_table("campaign_members") as batch_op:
        batch_op.drop_constraint("fk_campaign_members_user_id_users", type_="foreignkey")
        batch_op.create_foreign_key(
            op.f("fk_campaign_members_user_id_role_users"),
            "users",
            ["user_id", "role"],
            ["id", "role"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("campaign_members") as batch_op:
        batch_op.drop_constraint("fk_campaign_members_user_id_role_users", type_="foreignkey")
        batch_op.create_foreign_key(
            op.f("fk_campaign_members_user_id_users"),
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_id_role", type_="unique")
