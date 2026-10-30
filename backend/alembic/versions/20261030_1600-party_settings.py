"""The party settings table, with its one row.

Revision ID: party_settings
Revises: user_role_nullable
Create Date: 2026-10-30 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from backend.models.party import hex_colour

revision: str = "party_settings"
down_revision: str | None = "user_role_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "party_settings",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("short_name", sa.String(length=30), nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=False),
        sa.Column("primary_colour", sa.String(length=7), nullable=False),
        sa.Column("secondary_colour", sa.String(length=7), nullable=False),
        sa.Column("contact_email", sa.String(length=254), nullable=False),
        sa.Column("contact_phone", sa.String(length=20), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("manifesto_text", sa.Text(), nullable=False),
        sa.Column("manifesto_url", sa.String(length=500), nullable=False),
        sa.Column("social_links", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_party_settings_singleton")),
        sa.CheckConstraint(
            hex_colour("primary_colour"), name=op.f("ck_party_settings_primary_colour_hex")
        ),
        sa.CheckConstraint(
            hex_colour("secondary_colour"), name=op.f("ck_party_settings_secondary_colour_hex")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_settings")),
    )
    op.execute(
        "INSERT INTO party_settings (id, name, short_name, logo_url, primary_colour, "
        "secondary_colour, contact_email, contact_phone, address, description, "
        "manifesto_text, manifesto_url, social_links) VALUES "
        "(1, 'Party name', '', '', '#1f2937', '#f59e0b', '', '', '', '', '', '', '{}')"
    )


def downgrade() -> None:
    op.drop_table("party_settings")
