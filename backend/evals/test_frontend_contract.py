"""The API still offers everything the SPA reads and accepts everything it sends.

Checked against `contracts/frontend-api.json`, which both services read. The
unit tests would happily pass with a field renamed on one side only; this is
what fails when that happens.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from backend.main import app

CONTRACT = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "frontend-api.json").read_text()
)
OPENAPI: dict[str, Any] = app.openapi()

READS = sorted(CONTRACT["reads"])
NESTED = sorted(CONTRACT["nested_reads"])
WRITES = sorted(CONTRACT["writes"])
ENUMS = sorted(CONTRACT["enums"])


def _resolve(schema: dict[str, Any]) -> dict[str, Any]:
    """Follow a $ref, and look through a list or an optional to what it holds."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return _resolve(OPENAPI["components"]["schemas"][name])
    if schema.get("type") == "array":
        return _resolve(schema["items"])
    for key in ("anyOf", "allOf", "oneOf"):
        for option in schema.get(key, []):
            if option.get("type") != "null":
                return _resolve(option)
    return schema


def _operation(route: str) -> dict[str, Any]:
    method, path = route.split(" ", 1)
    paths = OPENAPI["paths"]
    assert path in paths, f"{path} is not served any more"
    operation = paths[path].get(method.lower())
    assert operation is not None, f"{path} no longer answers {method}"
    return operation


def _response_properties(route: str) -> dict[str, Any]:
    operation = _operation(route)
    ok = next(code for code in ("200", "201") if code in operation["responses"])
    schema = operation["responses"][ok]["content"]["application/json"]["schema"]
    return _resolve(schema).get("properties", {})


def _request_properties(route: str) -> dict[str, Any]:
    operation = _operation(route)
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    return _resolve(schema).get("properties", {})


@pytest.mark.parametrize("route", READS)
def test_every_field_the_spa_reads_is_still_returned(route: str) -> None:
    properties = _response_properties(route)
    missing = [name for name in CONTRACT["reads"][route] if name not in properties]
    assert not missing, f"{route} no longer returns {missing}"


@pytest.mark.parametrize("route", NESTED)
def test_every_nested_field_the_spa_reads_is_still_returned(route: str) -> None:
    outer, field = route.rsplit(".", 1)
    parent = _response_properties(outer)
    assert field in parent, f"{outer} no longer returns {field}"
    properties = _resolve(parent[field]).get("properties", {})
    missing = [name for name in CONTRACT["nested_reads"][route] if name not in properties]
    assert not missing, f"{route} no longer returns {missing}"


@pytest.mark.parametrize("route", WRITES)
def test_every_field_the_spa_sends_is_still_accepted(route: str) -> None:
    if "." in route.split(" ", 1)[1]:
        outer, field = route.rsplit(".", 1)
        parent = _request_properties(outer)
        assert field in parent, f"{outer} no longer accepts {field}"
        properties = _resolve(parent[field]).get("properties", {})
        unknown = [n for n in CONTRACT["writes"][route] if n not in properties]
        assert not unknown, f"{route} would reject {unknown}"
        return
    properties = _request_properties(route)
    unknown = [name for name in CONTRACT["writes"][route] if name not in properties]
    assert not unknown, f"{route} would reject {unknown}"


@pytest.mark.parametrize("key", ENUMS)
def test_the_stored_choice_strings_are_unchanged(key: str) -> None:
    from backend.models.enums import EventStatus, OfficeLevel, SupportLevel, UserRole
    from backend.models.enums import OperationalGrain as Grain

    if key == "user.create_role":
        assert set(CONTRACT["enums"][key]) < {m.value for m in UserRole}
        assert UserRole.CANDIDATE.value not in CONTRACT["enums"][key]
        return

    live = {
        "user.role": UserRole,
        "campaign.office_level": OfficeLevel,
        "event.status": EventStatus,
        "supporter.support_level": SupportLevel,
        "invite.support_levels": SupportLevel,
        "user.create_role": None,
        "setup.grain": Grain,
    }[key]
    assert sorted(m.value for m in live) == sorted(CONTRACT["enums"][key])


def test_the_routes_the_spa_calls_all_exist() -> None:
    called = set(CONTRACT["reads"]) | set(CONTRACT["writes"])
    for route in sorted(called):
        # A "." names a field inside a body, not a route of its own.
        if "." not in route.split(" ", 1)[1]:
            _operation(route)


def test_errors_arrive_as_one_readable_sentence() -> None:
    from backend.api.errors import _describe

    sentence = _describe({"loc": ["body", "consent_given"], "msg": "Consent is required."})
    assert isinstance(sentence, str)
    assert sentence == "consent_given: Consent is required."
