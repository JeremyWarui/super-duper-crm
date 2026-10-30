"""Record the consent channel and wording on supporters.

Revision ID: consent_on_supporters
Revises: audit_events
Create Date: 2026-10-30 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "consent_on_supporters"
down_revision: str | None = "audit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("supporters") as batch:
        batch.add_column(sa.Column("consent_channel", sa.String(length=20), nullable=True))
        batch.create_check_constraint(
            op.f("ck_supporters_consent_channel"),
            "consent_channel IN ('event_qr', 'campaign_link', 'mobilizer')",
        )
        batch.add_column(sa.Column("consent_wording", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("supporters") as batch:
        batch.drop_constraint(op.f("ck_supporters_consent_channel"), type_="check")
        batch.drop_column("consent_wording")
        batch.drop_column("consent_channel")
