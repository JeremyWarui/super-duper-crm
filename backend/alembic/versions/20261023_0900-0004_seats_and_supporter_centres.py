"""Each campaign names its seat; a supporter keeps their registration centre.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-23 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEATS = ("mca", "mp", "governor", "senator", "women_rep")
MATCH = (
    "(seat = 'mca' AND office_level = 'ward') "
    "OR (seat = 'mp' AND office_level = 'constituency') "
    "OR (seat IN ('governor', 'senator', 'women_rep') AND office_level = 'county')"
)


def upgrade() -> None:
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("seat", sa.String(length=20), nullable=True))
    op.execute(
        "UPDATE campaigns SET seat = CASE office_level "
        "WHEN 'ward' THEN 'mca' WHEN 'constituency' THEN 'mp' ELSE 'governor' END"
    )
    with op.batch_alter_table("campaigns") as batch:
        batch.alter_column("seat", existing_type=sa.String(length=20), nullable=False)
        batch.create_check_constraint(op.f("ck_campaigns_seat"), f"seat IN {SEATS}")
        batch.create_check_constraint(op.f("ck_campaigns_seat_matches_scope"), MATCH)

    with op.batch_alter_table("supporters") as batch:
        batch.add_column(sa.Column("registration_centre_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_supporters_registration_centre_id_registration_centres"),
            "registration_centres",
            ["registration_centre_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        op.f("ix_supporters_registration_centre_id"),
        "supporters",
        ["registration_centre_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_supporters_registration_centre_id"), table_name="supporters")
    with op.batch_alter_table("supporters") as batch:
        batch.drop_constraint(
            op.f("fk_supporters_registration_centre_id_registration_centres"), type_="foreignkey"
        )
        batch.drop_column("registration_centre_id")
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint(op.f("ck_campaigns_seat_matches_scope"), type_="check")
        batch.drop_constraint(op.f("ck_campaigns_seat"), type_="check")
        batch.drop_column("seat")
