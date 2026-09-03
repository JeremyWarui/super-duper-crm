"""Did the port keep everything the Django models had?

Graded against `django_parity.json`, a frozen inventory of the pre-port schema.
Every Django field must land in one of three buckets: mapped to a column,
listed in `renamed` with a new name that exists, or listed in `dropped` with a
written reason. Nothing may go missing quietly.

This is the reference check, so it is kept apart from `tests/`: those verify the
new code behaves, this verifies the new code is still the same application.
"""

import json
from pathlib import Path

import pytest

from backend.models import (
    Campaign,
    Constituency,
    County,
    Event,
    EventStatus,
    Mobilizer,
    OfficeLevel,
    PollingStation,
    RegistrationCentre,
    Supporter,
    SupportLevel,
    Target,
    User,
    UserRole,
    Ward,
)

REFERENCE = json.loads((Path(__file__).resolve().parent / "django_parity.json").read_text())

MAPPED_CLASSES = {
    "User": User,
    "County": County,
    "Constituency": Constituency,
    "Ward": Ward,
    "PollingStation": PollingStation,
    "RegistrationCentre": RegistrationCentre,
    "Campaign": Campaign,
    "Target": Target,
    "Mobilizer": Mobilizer,
    "Event": Event,
    "Supporter": Supporter,
}

MODEL_NAMES = sorted(REFERENCE["models"])


def _resolved_name(model_name: str, field_name: str, field_type: str) -> str:
    """The column a Django field is expected to have become."""
    renamed = REFERENCE["renamed"].get(f"{model_name}.{field_name}")
    if renamed:
        return renamed
    if field_type.startswith(("ForeignKey", "OneToOneField")):
        return f"{field_name}_id"
    return field_name


def test_every_django_model_became_a_mapped_class() -> None:
    assert set(MAPPED_CLASSES) == set(REFERENCE["models"])


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_table_name(model_name: str) -> None:
    expected = REFERENCE["models"][model_name]["table"]
    assert MAPPED_CLASSES[model_name].__tablename__ == expected


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_every_field_is_mapped_renamed_or_documented_as_dropped(model_name: str) -> None:
    columns = {c.name for c in MAPPED_CLASSES[model_name].__table__.columns}
    dropped = REFERENCE["dropped"]

    unaccounted = []
    for field_name, field_type in REFERENCE["models"][model_name]["fields"].items():
        key = f"{model_name}.{field_name}"
        if key in dropped:
            assert dropped[key].strip(), f"{key} is dropped with no reason recorded"
            continue
        if _resolved_name(model_name, field_name, field_type) not in columns:
            unaccounted.append(field_name)

    assert not unaccounted, (
        f"{model_name}: {unaccounted} exist in the Django models but have no column, "
        f"no entry in 'renamed', and no entry in 'dropped'."
    )


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_every_derived_property_survived(model_name: str) -> None:
    model = MAPPED_CLASSES[model_name]
    for name in REFERENCE["models"][model_name]["properties"]:
        assert hasattr(model, name), f"{model_name}.{name} was lost in the port"


def test_compute_win_number_survived_as_a_callable() -> None:
    """Django had it as a method. It is now a pure function plus a thin method,
    so both spellings must exist."""
    from backend.models import compute_win_number

    assert callable(compute_win_number)
    assert callable(Target.recompute_win_number)


def test_renames_point_at_columns_that_exist() -> None:
    """A rename entry is a promise; this checks the promise was kept."""
    for key, new_name in REFERENCE["renamed"].items():
        if key.startswith("_"):
            continue
        model_name, _ = key.split(".", 1)
        columns = {c.name for c in MAPPED_CLASSES[model_name].__table__.columns}
        assert new_name in columns, f"{key} claims to be renamed to a column that is missing"


def test_target_unique_constraints_survived_as_partial_indexes() -> None:
    """Django named them uniq_ward_target and uniq_center_target. The names
    changed to the project convention; the two rules must not have."""
    indexes = {i for i in Target.__table__.indexes if i.unique}
    by_columns = {tuple(sorted(c.name for c in i.columns)): i for i in indexes}

    ward_rule = by_columns.get(("campaign_id", "ward_id"))
    centre_rule = by_columns.get(("campaign_id", "registration_centre_id"))
    assert ward_rule is not None, "the ward-level uniqueness rule is gone"
    assert centre_rule is not None, "the centre-level uniqueness rule is gone"

    # Without the WHERE clause these two would conflict with each other.
    assert ward_rule.dialect_options["postgresql"]["where"] is not None
    assert centre_rule.dialect_options["postgresql"]["where"] is not None


@pytest.mark.parametrize(
    ("key", "enum_cls"),
    [
        ("User.Role", UserRole),
        ("Campaign.OfficeLevel", OfficeLevel),
        ("Event.Status", EventStatus),
        ("Supporter.SupportLevel", SupportLevel),
    ],
)
def test_choices_kept_their_values_and_labels(key: str, enum_cls: type) -> None:
    """Stored values are data already in the database; changing one silently
    orphans every existing row."""
    expected = [tuple(pair) for pair in REFERENCE["choices"][key]]
    assert enum_cls.choices() == expected
