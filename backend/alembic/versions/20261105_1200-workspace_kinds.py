"""Workspace kinds: party, hosted and standalone campaigns, and the national scope.

Revision ID: workspace_kinds
Revises: remove_hosting_finance
Create Date: 2026-11-05 12:00:00.000000

Every existing campaign becomes hosted. Downgrade refuses while a party or standalone campaign
exists, as the older schema has no place for it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "workspace_kinds"
down_revision: str | None = "remove_hosting_finance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "kind IN ('party', 'hosted', 'standalone')"
LEVELS = "office_level IN ('ward', 'constituency', 'county', 'national')"
OLD_LEVELS = "office_level IN ('ward', 'constituency', 'county')"
SEATS = (
    "(seat = 'mca' AND office_level = 'ward') "
    "OR (seat = 'mp' AND office_level = 'constituency') "
    "OR (seat IN ('governor', 'senator', 'women_rep') AND office_level = 'county')"
)
SEAT_MATCHES_SCOPE = (
    "(kind = 'party' AND seat IS NULL AND office_level = 'national') "
    f"OR (kind <> 'party' AND seat IS NOT NULL AND ({SEATS}))"
)
SINGLE_KINDS = "kind <> 'hosted'"
INDEX = "uq_campaigns_one_party_one_standalone"


def _checks(column: str, cli_name: str) -> list[str]:
    """The CHECKs on campaigns that name only this column of kind, seat and office_level.

    Looked up, as their names depend on how the table was first migrated.
    """
    if op.get_context().as_sql:
        # Rendered SQL names a CHECK as `alembic upgrade` creates it.
        return [cli_name]
    others = {"kind", "seat", "office_level"} - {column}
    return [
        check["name"]
        for check in sa.inspect(op.get_bind()).get_check_constraints("campaigns")
        if column in check["sqltext"] and not any(o in check["sqltext"] for o in others)
    ]


def upgrade() -> None:
    old_levels = _checks("office_level", "ck_campaigns_office_level")
    with op.batch_alter_table("campaigns") as batch:
        batch.add_column(sa.Column("kind", sa.String(20), nullable=False, server_default="hosted"))
        batch.alter_column("seat", existing_type=sa.String(20), nullable=True)
        batch.drop_constraint(op.f("ck_campaigns_seat_matches_scope"), type_="check")
        for old in old_levels:
            batch.drop_constraint(op.f(old), type_="check")
        batch.create_check_constraint(op.f("ck_campaigns_workspace_kind"), KINDS)
        batch.create_check_constraint(op.f("ck_campaigns_office_level"), LEVELS)
        batch.create_check_constraint(op.f("ck_campaigns_seat_matches_scope"), SEAT_MATCHES_SCOPE)
    with op.batch_alter_table("campaigns") as batch:
        batch.alter_column("kind", existing_type=sa.String(20), server_default=None)
    op.create_index(
        INDEX,
        "campaigns",
        ["kind"],
        unique=True,
        sqlite_where=sa.text(SINGLE_KINDS),
        postgresql_where=sa.text(SINGLE_KINDS),
    )


def downgrade() -> None:
    if not op.get_context().as_sql and op.get_bind().scalar(
        sa.text(f"SELECT count(*) FROM campaigns WHERE {SINGLE_KINDS}")
    ):
        raise RuntimeError("A party or standalone campaign exists; remove it before downgrading.")
    kinds = _checks("kind", "ck_campaigns_workspace_kind")
    levels = _checks("office_level", "ck_campaigns_office_level")
    op.drop_index(INDEX, table_name="campaigns")
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint(op.f("ck_campaigns_seat_matches_scope"), type_="check")
        for old in kinds + levels:
            batch.drop_constraint(op.f(old), type_="check")
        batch.drop_column("kind")
        batch.alter_column("seat", existing_type=sa.String(20), nullable=False)
        batch.create_check_constraint(op.f("ck_campaigns_office_level"), OLD_LEVELS)
        batch.create_check_constraint(op.f("ck_campaigns_seat_matches_scope"), SEATS)
