"""One-time sign-in links, and a log of every email.

Revision ID: login_links_and_email_log
Revises: payment_instructions_to_site
Create Date: 2026-11-06 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "login_links_and_email_log"
down_revision: str | None = "payment_instructions_to_site"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PURPOSES = "purpose IN ('invite', 'reset')"


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "login_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint(PURPOSES, name=op.f("ck_login_invites_link_purpose")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_login_invites_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_login_invites_token_hash")),
    )
    op.create_index(op.f("ix_login_invites_user_id"), "login_invites", ["user_id"])
    op.create_table(
        "email_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("to", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_log")),
    )
    op.create_index(op.f("ix_email_log_to"), "email_log", ["to"])


def downgrade() -> None:
    op.drop_index(op.f("ix_email_log_to"), table_name="email_log")
    op.drop_table("email_log")
    op.drop_index(op.f("ix_login_invites_user_id"), table_name="login_invites")
    op.drop_table("login_invites")
