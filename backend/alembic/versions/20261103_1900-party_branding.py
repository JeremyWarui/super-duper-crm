"""Party branding: the slogan and registration number the website header shows.

Revision ID: party_branding
Revises: member_logins
Create Date: 2026-11-03 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "party_branding"
down_revision: str | None = "member_logins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "party_settings", sa.Column("slogan", sa.String(150), nullable=False, server_default="")
    )
    op.add_column(
        "party_settings",
        sa.Column("registration_number", sa.String(40), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("party_settings", "registration_number")
    op.drop_column("party_settings", "slogan")
