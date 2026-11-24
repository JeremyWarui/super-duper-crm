"""A separate SMS opt-in on each contact, and support levels on each campaign text.

Contacts already on the register keep exactly the texting they had: an opt-in where the consent
they gave mentions SMS, texts or contact. Drafts waiting for approval leave out Opposed contacts.

Revision ID: sms_consent
Revises: public_events
Create Date: 2026-11-25 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "sms_consent"
down_revision: str | None = "public_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("supporters") as batch:
        batch.add_column(
            sa.Column("sms_consent", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(sa.Column("sms_consent_wording", sa.Text(), nullable=True))
    op.execute(
        "UPDATE supporters SET sms_consent = TRUE, sms_consent_wording = consent_wording "
        "WHERE consent_given AND ("
        "lower(consent_wording) LIKE '%sms%' OR lower(consent_wording) LIKE '%text%' "
        "OR lower(consent_wording) LIKE '%contact%')"
    )
    with op.batch_alter_table("campaign_messages") as batch:
        batch.add_column(
            sa.Column("support_levels", sa.JSON(), server_default="[]", nullable=False)
        )
    op.execute(
        """UPDATE campaign_messages SET support_levels = '["supporter", "undecided"]' """
        "WHERE status = 'draft'"
    )


def downgrade() -> None:
    with op.batch_alter_table("campaign_messages") as batch:
        batch.drop_column("support_levels")
    with op.batch_alter_table("supporters") as batch:
        batch.drop_column("sms_consent_wording")
        batch.drop_column("sms_consent")
