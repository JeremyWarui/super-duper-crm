"""Volunteer areas: the sample's ten areas, a member's polling station, and row owners.

Revision ID: volunteer_areas
Revises: volunteer_register
Create Date: 2026-11-03 11:00:00.000000

Old interests map to the new areas: mobilisation to mobilising_voters, social_media and
fundraising as they are, and the rest to other, with their labels in interest_other.
Downgrading maps back where it can and drops the areas that have no old value.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "volunteer_areas"
down_revision: str | None = "volunteer_register"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER = "(campaign_id IS NULL) = (member_id IS NOT NULL)"
SAME = {"mobilisation": "mobilising_voters", "social_media": "social_media"}
SAME["fundraising"] = "fundraising"
OTHER_LABELS = {
    "events": "Events",
    "communications": "Communications",
    "administration": "Administration",
    "polling_day": "Polling day",
}
BACK = {new: old for old, new in SAME.items()}


def _areas(interests: list[str]) -> tuple[list[str], str]:
    """The new areas and the Other text for a list of old interests."""
    areas: list[str] = []
    others: list[str] = []
    for interest in interests:
        if interest in SAME:
            areas.append(SAME[interest])
        elif interest in OTHER_LABELS:
            others.append(OTHER_LABELS[interest])
    if others:
        areas.append("other")
    return areas, ", ".join(others)[:100]


def _interests(areas: list[str], other: str) -> list[str]:
    """The old interests for a list of areas."""
    labels = {label: value for value, label in OTHER_LABELS.items()}
    found = [BACK[a] for a in areas if a in BACK]
    if "other" in areas:
        found += [labels[part] for part in other.split(", ") if part in labels]
    return found


def _rewrite(convert) -> None:
    """Apply `convert(interests, interest_other) -> (interests, interest_other)` to every row.

    Rendering SQL offline has no rows to read, so it writes nothing.
    """
    if op.get_context().as_sql:
        return
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, interests, interest_other FROM volunteer_profiles")
    ).all()
    for row_id, interests, other in rows:
        chosen = json.loads(interests) if isinstance(interests, str) else (interests or [])
        new, new_other = convert(chosen, other or "")
        connection.execute(
            sa.text(
                "UPDATE volunteer_profiles SET interests = :interests, "
                "interest_other = :other WHERE id = :id"
            ),
            {"interests": json.dumps(new), "other": new_other, "id": row_id},
        )


def upgrade() -> None:
    with op.batch_alter_table("party_members") as batch:
        batch.add_column(sa.Column("first_name", sa.String(75), nullable=True))
        batch.add_column(sa.Column("registration_centre_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_party_members_registration_centre_id_registration_centres"),
            "registration_centres",
            ["registration_centre_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    _rewrite(lambda interests, _other: _areas(interests))
    with op.batch_alter_table("volunteer_profiles") as batch:
        batch.create_check_constraint(op.f("ck_volunteer_profiles_owner"), OWNER)


def downgrade() -> None:
    with op.batch_alter_table("volunteer_profiles") as batch:
        batch.drop_constraint(op.f("ck_volunteer_profiles_owner"), type_="check")
    _rewrite(lambda areas, other: (_interests(areas, other), ""))
    with op.batch_alter_table("party_members") as batch:
        batch.drop_constraint(
            op.f("fk_party_members_registration_centre_id_registration_centres"),
            type_="foreignkey",
        )
        batch.drop_column("registration_centre_id")
        batch.drop_column("first_name")
