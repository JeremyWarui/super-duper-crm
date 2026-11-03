"""The website's news sign-ups, and the privacy notice they agree to.

Revision ID: subscribers
Revises: party_branding
Create Date: 2026-11-03 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "subscribers"
down_revision: str | None = "party_branding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "party_settings", sa.Column("privacy_notice", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "party_settings",
        sa.Column("privacy_notice_version", sa.String(20), nullable=False, server_default="1"),
    )
    op.create_table(
        "subscribers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact", sa.String(254), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("consent_wording", sa.Text(), nullable=False),
        sa.Column("notice_version", sa.String(20), nullable=False),
        sa.Column("unsubscribe_code", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("channel IN ('sms', 'email')", name=op.f("ck_subscribers_channel")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscribers")),
        sa.UniqueConstraint("contact", name=op.f("uq_subscribers_contact")),
        sa.UniqueConstraint("unsubscribe_code", name=op.f("uq_subscribers_unsubscribe_code")),
    )


def downgrade() -> None:
    op.drop_table("subscribers")
    op.drop_column("party_settings", "privacy_notice_version")
    op.drop_column("party_settings", "privacy_notice")
