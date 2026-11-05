"""Campaign code never imports party code (docs/Product_Design.md, "Principles" 3, PD-3)."""

import ast
import importlib
import importlib.util
import types
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

CAMPAIGN = [
    *(
        f"backend/api/routers/{name}.py"
        for name in (
            "campaigns",
            "targets",
            "mobilizers",
            "events",
            "supporters",
            "strategy",
            "team",
            "payments",
            "join",
            "workspace_site",
        )
    ),
    *(
        f"backend/services/{name}.py"
        for name in (
            "campaigns",
            "campaign_volunteers",
            "targets",
            "strategy",
            "team",
            "payouts",
            "payout_flow",
            "sms",
            "consent",
            "access",
            "permissions",
        )
    ),
    *(
        f"backend/models/{name}.py"
        for name in (
            "campaign",
            "membership",
            "event",
            "mobilizer",
            "supporter",
            "target",
            "payment",
            "volunteer",
        )
    ),
]
PARTY = (
    "backend.models.party",
    "backend.services.membership",
    "backend.services.aspirants",
    "backend.services.volunteers",
    "backend.services.party",
    "backend.services.party_workspace",
    "backend.api.routers.party",
)
ALLOWED = {
    # The hosted rule reads the aspirant's status.
    ("backend/services/access.py", "backend.models.party.Aspirant"),
    # Type-only: a party volunteer row names its member.
    ("backend/models/volunteer.py", "backend.models.party.PartyMember"),
}


def _is_party(module: str) -> bool:
    return any(module == party or module.startswith(f"{party}.") for party in PARTY) or (
        module.startswith("backend.api.routers.party_")
    )


def _origins(node: ast.Import | ast.ImportFrom, package: str) -> list[str]:
    """Where each imported name is defined: a module path, or module.name for an object."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    base = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
    origins = [base] if _is_party(base) else []
    for alias in node.names:
        package = importlib.import_module(base)
        found = getattr(package, alias.name, None)
        if isinstance(found, types.ModuleType):
            origins.append(found.__name__)
        elif found is not None and getattr(found, "__module__", None):
            origins.append(f"{found.__module__}.{alias.name}")
        else:
            origins.append(f"{base}.{alias.name}")
    return origins


def violations(relative: str, source: str) -> list[str]:
    """The party code this campaign module imports, as `module` or `module.Name`."""
    package = relative.removesuffix(".py").replace("/", ".").rpartition(".")[0]
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import | ast.ImportFrom):
            found += [
                origin
                for origin in _origins(node, package)
                if _is_party(origin) and (relative, origin) not in ALLOWED
            ]
    return found


@pytest.mark.parametrize("relative", CAMPAIGN)
def test_campaign_code_imports_no_party_code(relative: str) -> None:
    assert violations(relative, (SRC / relative).read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "planted",
    [
        "from backend.models import PartyMember",
        "from backend.models.party import Aspirant",
        "from backend.services import membership",
        "import backend.services.aspirants",
        "from backend.api.routers.party_members import router",
        "from .party_members import router",
        "from ...services import membership",
        "from ...models.party import Aspirant",
    ],
)
def test_a_planted_party_import_is_caught(planted: str) -> None:
    assert violations("backend/api/routers/campaigns.py", planted)
