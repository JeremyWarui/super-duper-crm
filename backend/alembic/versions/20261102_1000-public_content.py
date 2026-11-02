"""Public content: the party's leaders, and its news and events.

Revision ID: public_content
Revises: subscriptions
Create Date: 2026-11-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "public_content"
down_revision: str | None = "subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("(CURRENT_TIMESTAMP)"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "party_leaders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("position", sa.String(150), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("photo_url", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_leaders")),
    )
    op.create_table(
        "party_posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "news",
                "event",
                name="post_kind",
                native_enum=False,
                length=20,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("venue", sa.String(150), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            "(kind = 'event') = (event_date IS NOT NULL)",
            name=op.f("ck_party_posts_event_has_date"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_posts")),
    )
    op.create_index(
        "ix_party_posts_kind_published_event_date",
        "party_posts",
        ["kind", "published", "event_date"],
    )
    op.create_index(
        "ix_party_posts_kind_published_published_on",
        "party_posts",
        ["kind", "published", "published_on"],
    )


def downgrade() -> None:
    op.drop_table("party_posts")
    op.drop_table("party_leaders")
