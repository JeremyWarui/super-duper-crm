"""Agenda issues carry an optional photo for their homepage card.

Revision ID: issue_image
Revises: schema_20261107
"""

import sqlalchemy as sa
from alembic import op

revision: str = "issue_image"
down_revision: str | None = "schema_20261107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agenda_issues", sa.Column("image_url", sa.String(500), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("agenda_issues", "image_url")
