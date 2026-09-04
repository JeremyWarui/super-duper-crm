"""No field leaves the schema without a note saying why.

Checked against `schema_baseline.json`. Every field listed there must be a
column, a recorded rename, or a recorded drop.
"""

import json
from pathlib import Path

import pytest

from backend.models import (
    AuthToken,
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

BASELINE = json.loads((Path(__file__).resolve().parent / "schema_baseline.json").read_text())

MODELS = {
    "User": User,
    "AuthToken": AuthToken,
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

MODEL_NAMES = sorted(BASELINE["models"])


def _column_name(model_name: str, field_name: str, field_type: str) -> str:
    """The column a baseline field is expected to map to."""
    renamed = BASELINE["renamed"].get(f"{model_name}.{field_name}")
    if renamed:
        return renamed
    if field_type.endswith("reference"):
        return f"{field_name}_id"
    return field_name


def test_every_model_in_the_baseline_exists() -> None:
    assert set(MODELS) == set(BASELINE["models"])


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_table_name(model_name: str) -> None:
    assert MODELS[model_name].__tablename__ == BASELINE["models"][model_name]["table"]


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_every_field_is_mapped_renamed_or_recorded_as_dropped(model_name: str) -> None:
    columns = {c.name for c in MODELS[model_name].__table__.columns}
    dropped = BASELINE["dropped"]

    unaccounted = []
    for field_name, field_type in BASELINE["models"][model_name]["fields"].items():
        key = f"{model_name}.{field_name}"
        if key in dropped:
            assert dropped[key].strip(), f"{key} is dropped with no reason recorded"
            continue
        if _column_name(model_name, field_name, field_type) not in columns:
            unaccounted.append(field_name)

    assert not unaccounted, (
        f"{model_name}: {unaccounted} have no column, no rename, and no recorded drop."
    )


@pytest.mark.parametrize("model_name", MODEL_NAMES)
def test_every_calculated_value_still_exists(model_name: str) -> None:
    model = MODELS[model_name]
    for name in BASELINE["models"][model_name]["properties"]:
        assert hasattr(model, name), f"{model_name}.{name} is gone"


def test_compute_win_number_is_available() -> None:
    from backend.models import compute_win_number

    assert callable(compute_win_number)
    assert callable(Target.recompute_win_number)


def test_renames_point_at_columns_that_exist() -> None:
    for key, new_name in BASELINE["renamed"].items():
        if key.startswith("_"):
            continue
        model_name, _ = key.split(".", 1)
        columns = {c.name for c in MODELS[model_name].__table__.columns}
        assert new_name in columns, f"{key} renames to a column that is missing"


def test_target_keeps_both_uniqueness_rules() -> None:
    indexes = {i for i in Target.__table__.indexes if i.unique}
    by_columns = {tuple(sorted(c.name for c in i.columns)): i for i in indexes}

    ward_rule = by_columns.get(("campaign_id", "ward_id"))
    centre_rule = by_columns.get(("campaign_id", "registration_centre_id"))
    assert ward_rule is not None, "the ward-level rule is gone"
    assert centre_rule is not None, "the centre-level rule is gone"

    # Without the WHERE clause these two rules would conflict.
    assert ward_rule.dialect_options["postgresql"]["where"] is not None
    assert centre_rule.dialect_options["postgresql"]["where"] is not None


@pytest.mark.parametrize(
    ("key", "enum_cls"),
    [
        ("UserRole", UserRole),
        ("OfficeLevel", OfficeLevel),
        ("EventStatus", EventStatus),
        ("SupportLevel", SupportLevel),
    ],
)
def test_choices_keep_their_stored_values(key: str, enum_cls: type) -> None:
    expected = [tuple(pair) for pair in BASELINE["choices"][key]]
    assert enum_cls.choices() == expected
