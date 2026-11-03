"""Homepage content: the hero carousel's slides and the agenda's issues.

Revision ID: home_content
Revises: branches
Create Date: 2026-11-03 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "home_content"
down_revision: str | None = "branches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "hero_slides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("kicker", sa.String(80), nullable=False, server_default=""),
        sa.Column("headline", sa.String(120), nullable=False),
        sa.Column("line", sa.String(300), nullable=False, server_default=""),
        sa.Column("button_label", sa.String(40), nullable=False, server_default=""),
        sa.Column("button_url", sa.String(500), nullable=False, server_default=""),
        *_stamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hero_slides")),
    )
    op.create_table(
        "agenda_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False, server_default=""),
        sa.Column("what_we_will_do", sa.Text(), nullable=False, server_default=""),
        sa.Column("why_it_matters", sa.Text(), nullable=False, server_default=""),
        *_stamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agenda_issues")),
    )


def downgrade() -> None:
    op.drop_table("agenda_issues")
    op.drop_table("hero_slides")
