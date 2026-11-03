"""News pages: post labels, authors, statement records, event counties, and party documents.

Revision ID: news_pages
Revises: home_content
Create Date: 2026-11-04 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "news_pages"
down_revision: str | None = "home_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("party_posts") as batch:
        batch.add_column(
            sa.Column(
                "label",
                sa.Enum(
                    "statement",
                    "news",
                    "opinion",
                    name="post_label",
                    native_enum=False,
                    length=20,
                    create_constraint=True,
                ),
                nullable=False,
                server_default="news",
            )
        )
        batch.add_column(sa.Column("place", sa.String(80), nullable=False, server_default=""))
        batch.add_column(sa.Column("author", sa.String(150), nullable=False, server_default=""))
        batch.add_column(
            sa.Column("author_photo_url", sa.String(500), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("reference", sa.String(40), nullable=False, server_default=""))
        batch.add_column(sa.Column("pdf_url", sa.String(500), nullable=False, server_default=""))
        batch.add_column(sa.Column("county_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_party_posts_county_id_counties"),
            "counties",
            ["county_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_table(
        "party_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_documents")),
    )


def downgrade() -> None:
    op.drop_table("party_documents")
    with op.batch_alter_table("party_posts") as batch:
        batch.drop_constraint(op.f("fk_party_posts_county_id_counties"), type_="foreignkey")
        for name in ("county_id", "pdf_url", "reference", "author_photo_url", "author", "place"):
            batch.drop_column(name)
        batch.drop_constraint("post_label", type_="check")
        batch.drop_column("label")
