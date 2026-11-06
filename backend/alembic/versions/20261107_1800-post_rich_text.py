"""Post text is HTML from the editor: existing plain-text bodies become paragraphs.

Revision ID: post_rich_text
Revises: party_messages
Create Date: 2026-11-07 18:00:00.000000
"""

import html
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "post_rich_text"
down_revision: str | None = "party_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POSTS = sa.table("party_posts", sa.column("id", sa.Uuid), sa.column("body", sa.Text))
BLOCK_END = re.compile(r"</(p|h2|h3|li|blockquote)>|<br\s*/?>", re.IGNORECASE)
TAG = re.compile(r"<[^>]*>")


def _html(text: str) -> str:
    lines = (line.strip() for line in text.split("\n"))
    return "".join(f"<p>{html.escape(line, quote=False)}</p>" for line in lines if line)


def _plain(body: str) -> str:
    lines = (
        line.strip() for line in html.unescape(TAG.sub("", BLOCK_END.sub("\n", body))).split("\n")
    )
    return "\n\n".join(line for line in lines if line)


def _rewrite(convert, wanted) -> None:
    """Rewrite each body `wanted` picks; rendering SQL offline reads no rows, so it skips."""
    if op.get_context().as_sql:
        return
    bind = op.get_bind()
    for row in bind.execute(sa.select(POSTS.c.id, POSTS.c.body)).all():
        if row.body and wanted(row.body):
            bind.execute(POSTS.update().where(POSTS.c.id == row.id).values(body=convert(row.body)))


def upgrade() -> None:
    _rewrite(_html, lambda body: True)


def downgrade() -> None:
    _rewrite(_plain, lambda body: body.lstrip().startswith("<"))
