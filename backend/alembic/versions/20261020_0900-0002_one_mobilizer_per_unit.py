"""A mobilizer's ward is optional, and a unit holds at most one mobilizer.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WARD_UNIT = "ward_id IS NOT NULL AND registration_centre_id IS NULL"
CENTRE_UNIT = "registration_centre_id IS NOT NULL"


def upgrade() -> None:
    with op.batch_alter_table("mobilizers") as batch:
        batch.alter_column("ward_id", existing_type=sa.Uuid(), nullable=True)
    op.create_index(
        "uq_mobilizers_campaign_ward",
        "mobilizers",
        ["campaign_id", "ward_id"],
        unique=True,
        postgresql_where=sa.text(WARD_UNIT),
        sqlite_where=sa.text(WARD_UNIT),
    )
    op.create_index(
        "uq_mobilizers_campaign_registration_centre",
        "mobilizers",
        ["campaign_id", "registration_centre_id"],
        unique=True,
        postgresql_where=sa.text(CENTRE_UNIT),
        sqlite_where=sa.text(CENTRE_UNIT),
    )


def downgrade() -> None:
    """Fails while any mobilizer has no ward."""
    op.drop_index("uq_mobilizers_campaign_registration_centre", table_name="mobilizers")
    op.drop_index("uq_mobilizers_campaign_ward", table_name="mobilizers")
    with op.batch_alter_table("mobilizers") as batch:
        batch.alter_column("ward_id", existing_type=sa.Uuid(), nullable=False)
