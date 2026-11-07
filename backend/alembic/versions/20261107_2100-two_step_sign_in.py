"""2-step sign-in and Google sign-in: authenticator secrets, the session's 2-step mark, a
one-time Google handoff, and the staff 2-step switch.

Revision ID: two_step_sign_in
Revises: data_protection
Create Date: 2026-11-07 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "two_step_sign_in"
down_revision: str | None = "data_protection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_totp",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("secret", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_step", sa.Integer(), nullable=False),
        sa.Column("recovery_hashes", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_totp_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_totp")),
    )
    with op.batch_alter_table("auth_tokens") as batch:
        batch.add_column(
            sa.Column("two_step", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(sa.Column("handoff_hash", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column("handoff_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_unique_constraint(op.f("uq_auth_tokens_handoff_hash"), ["handoff_hash"])
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(
            sa.Column(
                "staff_two_step_required", sa.Boolean(), server_default=sa.false(), nullable=False
            )
        )
    op.execute(
        "UPDATE site_settings SET staff_two_step_required = TRUE "
        "WHERE organisation_type = 'party'"
    )


def downgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("staff_two_step_required")
    with op.batch_alter_table("auth_tokens") as batch:
        batch.drop_constraint(op.f("uq_auth_tokens_handoff_hash"), type_="unique")
        batch.drop_column("handoff_expires_at")
        batch.drop_column("handoff_hash")
        batch.drop_column("two_step")
    op.drop_table("user_totp")
