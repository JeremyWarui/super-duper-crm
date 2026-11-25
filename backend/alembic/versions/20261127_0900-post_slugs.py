"""News posts get a readable address: posts.slug, filled from each title.

Revision ID: post_slugs
Revises: drop_google_handoff
Create Date: 2026-11-27 09:00:00

"""

import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "post_slugs"
down_revision: str | None = "drop_google_handoff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _slug_of(title: str) -> str:
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:80].rstrip("-") or "post"


def upgrade() -> None:
    with op.batch_alter_table("posts") as batch:
        batch.add_column(sa.Column("slug", sa.String(length=90), nullable=True))
        batch.create_unique_constraint("uq_posts_slug", ["slug"])
    if op.get_context().as_sql:
        return
    bind = op.get_bind()
    taken: set[str] = set()
    rows = bind.execute(sa.text("SELECT id, title FROM posts ORDER BY created_at, id")).all()
    for post_id, title in rows:
        base = slug = _slug_of(title)
        n = 1
        while slug in taken:
            n += 1
            slug = f"{base}-{n}"
        taken.add(slug)
        bind.execute(sa.text("UPDATE posts SET slug = :slug WHERE id = :id"), {"slug": slug, "id": post_id})


def downgrade() -> None:
    with op.batch_alter_table("posts") as batch:
        batch.drop_constraint("uq_posts_slug", type_="unique")
        batch.drop_column("slug")
