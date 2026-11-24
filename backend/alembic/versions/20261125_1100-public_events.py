"""Publish a campaign event on the public website, with a description and a photo.

Revision ID: public_events
Revises: announcements
Create Date: 2026-11-25 11:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "public_events"
down_revision: str | None = "announcements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.add_column(
            sa.Column("published", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(sa.Column("description", sa.Text(), server_default="", nullable=False))
        batch.add_column(
            sa.Column("image_url", sa.String(length=500), server_default="", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.drop_column("image_url")
        batch.drop_column("description")
        batch.drop_column("published")
