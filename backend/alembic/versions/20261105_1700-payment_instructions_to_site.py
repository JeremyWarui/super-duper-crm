"""Payment instructions move from the party settings to the site settings.

Revision ID: payment_instructions_to_site
Revises: stored_files
Create Date: 2026-11-05 17:00:00.000000

The Contribute page of either organisation type shows them. The party's text is copied over.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "payment_instructions_to_site"
down_revision: str | None = "stored_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column() -> sa.Column:
    return sa.Column("payment_instructions", sa.Text(), nullable=False, server_default="")


def upgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(_column())
    op.execute(
        "UPDATE site_settings SET payment_instructions = COALESCE("
        "(SELECT payment_instructions FROM party_settings WHERE party_settings.id = 1), '')"
    )
    with op.batch_alter_table("party_settings") as batch:
        batch.drop_column("payment_instructions")


def downgrade() -> None:
    with op.batch_alter_table("party_settings") as batch:
        batch.add_column(_column())
    op.execute(
        "UPDATE party_settings SET payment_instructions = COALESCE("
        "(SELECT payment_instructions FROM site_settings WHERE site_settings.id = 1), '')"
    )
    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("payment_instructions")
