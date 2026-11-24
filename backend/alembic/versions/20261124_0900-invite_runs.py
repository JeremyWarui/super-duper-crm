"""Event invitations go through the SMS queue: a run may belong to an event.

Revision ID: invite_runs
Revises: meetings_push
Create Date: 2026-11-24 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "invite_runs"
down_revision: str | None = "meetings_push"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sms_runs") as batch:
        batch.add_column(sa.Column("event_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_sms_runs_event_id_events"), "events", ["event_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("sms_runs") as batch:
        batch.drop_constraint(op.f("fk_sms_runs_event_id_events"), type_="foreignkey")
        batch.drop_column("event_id")
