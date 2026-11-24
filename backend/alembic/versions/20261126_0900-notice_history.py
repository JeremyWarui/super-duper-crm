"""Notices keep who sent them and a preview line; announcement notices take their announcement's
author, first line and time.

Revision ID: notice_history
Revises: sms_consent
Create Date: 2026-11-26 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "notice_history"
down_revision: str | None = "sms_consent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notices") as batch:
        batch.add_column(sa.Column("detail", sa.Text(), server_default="", nullable=False))
        batch.add_column(sa.Column("sender_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_notices_sender_id_users", "users", ["sender_id"], ["id"], ondelete="SET NULL"
        )
    op.execute(
        "UPDATE notices SET "
        "sender_id = (SELECT a.author_id FROM announcements a WHERE a.id = notices.announcement_id), "
        "created_at = (SELECT a.created_at FROM announcements a "
        "WHERE a.id = notices.announcement_id) "
        "WHERE announcement_id IS NOT NULL"
    )
    if op.get_context().as_sql:
        return  # a rendered script has no rows to read; previews fill in as notices are sent
    bind = op.get_bind()
    bodies = bind.execute(sa.text("SELECT id, body FROM announcements")).all()
    for announcement_id, body in bodies:
        bind.execute(
            sa.text("UPDATE notices SET detail = :detail WHERE announcement_id = :id"),
            {"detail": _first_line(body), "id": announcement_id},
        )


def _first_line(text: str | None) -> str:
    """The first non-blank line, cut to 200 characters."""
    first = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    return first if len(first) <= 200 else first[:199].rstrip() + "…"


def downgrade() -> None:
    with op.batch_alter_table("notices") as batch:
        batch.drop_constraint("fk_notices_sender_id_users", type_="foreignkey")
        batch.drop_column("sender_id")
        batch.drop_column("detail")
