"""A Presidential seat contested over the whole country, and coordinator areas that take whole
counties and constituencies.

Revision ID: president
Revises: aspirant_only
"""

import sqlalchemy as sa
from alembic import op

revision: str = "president"
down_revision: str | None = "aspirant_only"
branch_labels = None
depends_on = None

SEATS = ["mca", "mp", "governor", "senator", "women_rep"]
SEAT_MATCHES_SCOPE = (
    "(seat = 'mca' AND office_level = 'ward') "
    "OR (seat = 'mp' AND office_level = 'constituency') "
    "OR (seat IN ('governor', 'senator', 'women_rep') AND office_level = 'county')"
)
PRESIDENT_MATCHES_SCOPE = (
    f"{SEAT_MATCHES_SCOPE} OR (seat = 'president' AND office_level = 'national')"
)
AREA_COLUMNS = ("county_id", "constituency_id", "ward_id", "registration_centre_id")
ONE_OF_FOUR = (
    " + ".join(f"(CASE WHEN {c} IS NULL THEN 0 ELSE 1 END)" for c in AREA_COLUMNS) + " = 1"
)
ONE_OF_TWO = "(ward_id IS NULL) <> (registration_centre_id IS NULL)"
NEW_PLACES = {"county_id": "counties", "constituency_id": "constituencies"}


def _enum_check(table: str, enum: str) -> str:
    """The name an enum's CHECK carries: prefixed under the models' naming convention, bare
    otherwise."""
    target = op.get_context().opts.get("target_metadata")
    named = getattr(target, "naming_convention", {}).get("ck")
    return op.f(f"ck_{table}_{enum}" if named else enum)


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _campaign_checks(seats: list[str], scope: str) -> None:
    with op.batch_alter_table("campaigns") as batch:
        batch.drop_constraint(op.f("ck_campaigns_seat_matches_scope"), type_="check")
        batch.drop_constraint(_enum_check("campaigns", "seat"), type_="check")
        batch.create_check_constraint(_enum_check("campaigns", "seat"), _in("seat", seats))
        batch.create_check_constraint(op.f("ck_campaigns_seat_matches_scope"), scope)


def upgrade() -> None:
    _campaign_checks([*SEATS, "president"], PRESIDENT_MATCHES_SCOPE)
    with op.batch_alter_table("campaign_member_areas") as batch:
        batch.drop_constraint(op.f("ck_campaign_member_areas_one_place"), type_="check")
        for column, table in NEW_PLACES.items():
            batch.add_column(sa.Column(column, sa.Uuid(), nullable=True))
            batch.create_foreign_key(
                op.f(f"fk_campaign_member_areas_{column}_{table}"),
                table,
                [column],
                ["id"],
                ondelete="RESTRICT",
            )
            batch.create_unique_constraint(
                op.f(f"uq_campaign_member_areas_campaign_member_id_{column}"),
                ["campaign_member_id", column],
            )
        batch.create_check_constraint(op.f("ck_campaign_member_areas_one_place"), ONE_OF_FOUR)


def downgrade() -> None:
    op.execute(
        "DELETE FROM campaign_member_areas WHERE ward_id IS NULL AND registration_centre_id IS NULL"
    )
    with op.batch_alter_table("campaign_member_areas") as batch:
        batch.drop_constraint(op.f("ck_campaign_member_areas_one_place"), type_="check")
        for column, table in NEW_PLACES.items():
            batch.drop_constraint(
                op.f(f"uq_campaign_member_areas_campaign_member_id_{column}"), type_="unique"
            )
            batch.drop_constraint(
                op.f(f"fk_campaign_member_areas_{column}_{table}"), type_="foreignkey"
            )
            batch.drop_column(column)
        batch.create_check_constraint(op.f("ck_campaign_member_areas_one_place"), ONE_OF_TWO)
    op.execute("DELETE FROM campaigns WHERE seat = 'president'")
    _campaign_checks(SEATS, SEAT_MATCHES_SCOPE)
