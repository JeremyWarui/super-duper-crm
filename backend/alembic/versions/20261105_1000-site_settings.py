"""Site settings and the organisation type, split out of the party settings.

Revision ID: site_settings
Revises: payout_approval
Create Date: 2026-11-05 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from backend.models.party import hex_colour

revision: str = "site_settings"
down_revision: str | None = "payout_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The columns that move, with their types, in table order.
MOVED = (
    ("name", sa.String(150)),
    ("short_name", sa.String(30)),
    ("slogan", sa.String(150)),
    ("about_headline", sa.String(150)),
    ("logo_url", sa.String(500)),
    ("primary_colour", sa.String(7)),
    ("secondary_colour", sa.String(7)),
    ("contact_email", sa.String(254)),
    ("contact_phone", sa.String(20)),
    ("address", sa.String(300)),
    ("social_links", sa.JSON()),
    ("description", sa.Text()),
    ("manifesto_text", sa.Text()),
    ("manifesto_url", sa.String(500)),
    ("privacy_notice", sa.Text()),
    ("privacy_notice_version", sa.String(20)),
)
NAMES = [name for name, _ in MOVED]


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column(
            "organisation_type",
            sa.Enum(
                "party",
                "aspirant",
                name="organisation_type",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("short_name", sa.String(30), nullable=False),
        sa.Column("slogan", sa.String(150), nullable=False, server_default=""),
        sa.Column("about_headline", sa.String(150), nullable=False, server_default=""),
        sa.Column("logo_url", sa.String(500), nullable=False),
        sa.Column("primary_colour", sa.String(7), nullable=False),
        sa.Column("secondary_colour", sa.String(7), nullable=False),
        sa.Column("contact_email", sa.String(254), nullable=False),
        sa.Column("contact_phone", sa.String(20), nullable=False),
        sa.Column("address", sa.String(300), nullable=False),
        sa.Column("social_links", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("manifesto_text", sa.Text(), nullable=False),
        sa.Column("manifesto_url", sa.String(500), nullable=False),
        sa.Column("privacy_notice", sa.Text(), nullable=False, server_default=""),
        sa.Column("privacy_notice_version", sa.String(20), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_site_settings_singleton")),
        sa.CheckConstraint(
            hex_colour("primary_colour"), name=op.f("ck_site_settings_primary_colour_hex")
        ),
        sa.CheckConstraint(
            hex_colour("secondary_colour"), name=op.f("ck_site_settings_secondary_colour_hex")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_settings")),
    )
    # Every installation so far is a party.
    columns = ", ".join(NAMES)
    op.execute(
        f"INSERT INTO site_settings (id, organisation_type, {columns}, updated_at) "
        f"SELECT 1, 'party', {columns}, updated_at FROM party_settings WHERE id = 1"
    )
    with op.batch_alter_table("party_settings") as batch:
        batch.drop_constraint(op.f("ck_party_settings_primary_colour_hex"), type_="check")
        batch.drop_constraint(op.f("ck_party_settings_secondary_colour_hex"), type_="check")
        for name in NAMES:
            batch.drop_column(name)
        batch.add_column(
            sa.Column("hosting_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    with op.batch_alter_table("party_settings") as batch:
        batch.drop_column("hosting_enabled")
        for name, type_ in MOVED:
            default = "{}" if name == "social_links" else ("1" if name.endswith("version") else "")
            batch.add_column(sa.Column(name, type_, nullable=False, server_default=default))
    assignments = ", ".join(f"{n} = (SELECT {n} FROM site_settings WHERE id = 1)" for n in NAMES)
    op.execute(
        f"UPDATE party_settings SET {assignments} "
        "WHERE EXISTS (SELECT 1 FROM site_settings WHERE id = 1)"
    )
    # The colour checks go on once the copied colours are in place.
    with op.batch_alter_table("party_settings") as batch:
        batch.create_check_constraint(
            op.f("ck_party_settings_primary_colour_hex"), hex_colour("primary_colour")
        )
        batch.create_check_constraint(
            op.f("ck_party_settings_secondary_colour_hex"), hex_colour("secondary_colour")
        )
    op.drop_table("site_settings")
