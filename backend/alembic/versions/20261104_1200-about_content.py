"""About-page content: the party's headline and founding year, its values and its organs.

Revision ID: about_content
Revises: news_pages
Create Date: 2026-11-04 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "about_content"
down_revision: str | None = "news_pages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("party_values", "party_organs")


def upgrade() -> None:
    with op.batch_alter_table("party_settings") as batch:
        batch.add_column(
            sa.Column("about_headline", sa.String(150), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("founded_year", sa.String(4), nullable=False, server_default=""))
    for table in TABLES:
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(150), nullable=False),
            sa.Column("text", sa.String(300), nullable=False, server_default=""),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
    with op.batch_alter_table("party_settings") as batch:
        batch.drop_column("founded_year")
        batch.drop_column("about_headline")
