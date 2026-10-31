"""Party offices only on staff logins, and a login's link to its party member.

Revision ID: staff_kind
Revises: volunteer_profiles
Create Date: 2026-11-01 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "staff_kind"
down_revision: str | None = "volunteer_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def _refuse_offices_on_campaign_logins() -> None:
    if op.get_context().as_sql:
        return
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT r.user_id FROM party_roles r JOIN users u ON u.id = r.user_id "
                "WHERE u.role IS NOT NULL ORDER BY r.user_id"
            )
        )
        .all()
    )
    if rows:
        ids = ", ".join(str(row[0]) for row in rows)
        raise RuntimeError(f"Logins with a campaign role that hold a party office: {ids}")


def upgrade() -> None:
    _refuse_offices_on_campaign_logins()
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("kind", sa.String(8), nullable=True))
        batch_op.add_column(sa.Column("party_member_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE users SET kind = CASE WHEN role IS NULL THEN 'staff' ELSE 'campaign' END")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("kind", existing_type=sa.String(8), nullable=False)
        batch_op.create_check_constraint(
            op.f("ck_users_user_kind"), "kind IN ('campaign', 'staff')"
        )
        batch_op.create_check_constraint(
            op.f("ck_users_kind_matches_role"), "(kind = 'staff') = (role IS NULL)"
        )
        batch_op.create_unique_constraint(op.f("uq_users_id_kind"), ["id", "kind"])
        batch_op.create_foreign_key(
            op.f("fk_users_party_member_id_party_members"),
            "party_members",
            ["party_member_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("party_roles") as batch_op:
        batch_op.add_column(
            sa.Column("kind", sa.String(8), server_default="staff", nullable=False)
        )
        batch_op.create_check_constraint(op.f("ck_party_roles_kind_is_staff"), "kind = 'staff'")
        batch_op.drop_constraint("fk_party_roles_user_id_users", type_="foreignkey")
        batch_op.create_foreign_key(
            op.f("fk_party_roles_user_id_kind_users"),
            "users",
            ["user_id", "kind"],
            ["id", "kind"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("party_roles") as batch_op:
        batch_op.drop_constraint("fk_party_roles_user_id_kind_users", type_="foreignkey")
        batch_op.create_foreign_key(
            op.f("fk_party_roles_user_id_users"),
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_constraint("ck_party_roles_kind_is_staff", type_="check")
        batch_op.drop_column("kind")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_party_member_id_party_members", type_="foreignkey")
        batch_op.drop_constraint("uq_users_id_kind", type_="unique")
        batch_op.drop_constraint("ck_users_kind_matches_role", type_="check")
        batch_op.drop_constraint("ck_users_user_kind", type_="check")
        batch_op.drop_column("party_member_id")
        batch_op.drop_column("kind")
