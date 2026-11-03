"""Member logins: a party member's own login, and email as the sign-in name.

Revision ID: member_logins
Revises: volunteer_areas
Create Date: 2026-11-03 14:00:00.000000

Emails are trimmed and lower-cased. The upgrade stops, naming them, when two logins share an
email; give one of them another email (`campaign-crm set-email`) and run it again.
Downgrading deletes member logins.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "member_logins"
down_revision: str | None = "volunteer_areas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HAS_EMAIL = "email <> ''"
MEMBER = "kind = 'member'"


def upgrade() -> None:
    op.execute("UPDATE users SET email = lower(trim(email))")
    if not op.get_context().as_sql:
        shared = op.get_bind().execute(
            sa.text(
                "SELECT email, min(username), max(username) FROM users "
                "WHERE email <> '' GROUP BY email HAVING count(*) > 1"
            )
        ).all()
        if shared:
            names = "; ".join(f"{email}: {a}, {b}" for email, a, b in shared)
            raise RuntimeError(f"Logins share an email, which signs in: {names}.")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint(op.f("ck_users_user_kind"), type_="check")
        batch.drop_constraint(op.f("ck_users_kind_matches_role"), type_="check")
        batch.create_check_constraint(
            op.f("ck_users_user_kind"), "kind IN ('campaign', 'staff', 'member')"
        )
        batch.create_check_constraint(
            op.f("ck_users_kind_matches_role"), "(kind = 'campaign') = (role IS NOT NULL)"
        )
    op.create_index(
        "uq_users_email",
        "users",
        ["email"],
        unique=True,
        sqlite_where=sa.text(HAS_EMAIL),
        postgresql_where=sa.text(HAS_EMAIL),
    )
    op.create_index(
        "uq_users_member_login",
        "users",
        ["party_member_id"],
        unique=True,
        sqlite_where=sa.text(MEMBER),
        postgresql_where=sa.text(MEMBER),
    )


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE kind = 'member'")
    op.drop_index("uq_users_member_login", table_name="users")
    op.drop_index("uq_users_email", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint(op.f("ck_users_kind_matches_role"), type_="check")
        batch.drop_constraint(op.f("ck_users_user_kind"), type_="check")
        batch.create_check_constraint(op.f("ck_users_user_kind"), "kind IN ('campaign', 'staff')")
        batch.create_check_constraint(
            op.f("ck_users_kind_matches_role"), "(kind = 'staff') = (role IS NULL)"
        )
