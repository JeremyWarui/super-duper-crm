"""One-time tokens that open the first-run setup.

A database nobody has signed up to yet loses the placeholder site settings row the earlier
revisions copy in, so its first start opens the setup instead of being a party already.

Revision ID: setup_tokens
Revises: assignments_and_payment_routing
Create Date: 2026-11-07 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "setup_tokens"
down_revision: str | None = "assignments_and_payment_routing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "setup_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_setup_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_setup_tokens_token_hash")),
    )
    op.execute("DELETE FROM site_settings WHERE NOT EXISTS (SELECT 1 FROM users)")


def downgrade() -> None:
    # The earlier revisions expect the placeholder row back.
    op.execute(
        "INSERT INTO site_settings (id, organisation_type, name, short_name, logo_url, "
        "primary_colour, secondary_colour, contact_email, contact_phone, address, social_links, "
        "description, manifesto_text, manifesto_url) "
        "SELECT 1, 'party', 'Party name', '', '', '#1f2937', '#f59e0b', '', '', '', '{}', '', '', '' "
        "WHERE NOT EXISTS (SELECT 1 FROM site_settings)"
    )
    op.drop_table("setup_tokens")
