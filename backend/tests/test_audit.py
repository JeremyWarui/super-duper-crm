"""The audit trail: written in the caller's transaction, read by a superuser only."""

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent, UserRole
from backend.services.audit import record
from tests.conftest import World
from tests.factories import make_user


async def test_an_action_that_rolls_back_leaves_no_audit_row(session: AsyncSession) -> None:
    record(session, actor=None, action="campaign.create", subject_type="campaign")
    await session.rollback()

    assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_only_a_superuser_reads_the_audit_trail(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict[str, str],
) -> None:
    record(session, actor=None, action="campaign.create", subject_type="campaign")
    await session.commit()

    refused = await client.get("/api/admin/audit/", headers=world.headers("manager"))
    read = await client.get("/api/admin/audit/", headers=admin_headers)

    assert refused.status_code == 403
    assert [(e["action"], e["actor_name"]) for e in read.json()] == [("campaign.create", "cli")]


ACTIONS = [
    ("campaign.rename", "campaign", "patch", "/admin/campaigns/{campaign}/", "root"),
    ("campaign.delete", "campaign", "delete", "/admin/campaigns/{campaign}/", "root"),
    ("user.create", "user", "post", "/admin/users/", "root"),
    ("user.reset_password", "user", "post", "/admin/users/{mobilizer}/reset-password/", "root"),
    ("user.deactivate", "user", "post", "/admin/users/{mobilizer}/active/", "root"),
    ("user.activate", "user", "post", "/admin/users/{mobilizer}/active/", "root"),
    ("user.email", "user", "put", "/admin/users/{mobilizer}/email/", "root"),
    ("member.add", "user", "post", "/admin/campaigns/{campaign}/members/", "root"),
    ("member.remove", "user", "delete", "/admin/campaigns/{campaign}/members/{mobilizer}/", "root"),
    ("team.set_manager", "user", "post", "/campaigns/{campaign}/team/manager/", "jane"),
    ("mobilizer_login.create", "user", "post", "/users/", "amina"),
    ("mobilizer_login.delete", "user", "delete", "/users/{mobilizer}/", "amina"),
]


@pytest.mark.parametrize(("action", "subject_type", "method", "path", "actor"), ACTIONS)
async def test_each_console_and_team_action_writes_its_event(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict[str, str],
    action: str,
    subject_type: str,
    method: str,
    path: str,
    actor: str,
) -> None:
    spare = await make_user(session, username="spare", role=UserRole.MOBILIZER)
    ids = {"campaign": world.campaign.id, "mobilizer": world.mobilizer_user.id}
    bodies = {
        "campaign.rename": {"title": "Renamed"},
        "user.create": {"username": "fresh", "role": "manager"},
        "user.reset_password": {},
        "user.deactivate": {"active": False},
        "user.activate": {"active": True},
        "user.email": {"email": "juma.new@example.test"},
        "member.add": {"user": str(spare.id)},
        "team.set_manager": {"username": "wanjiru", "replace": True},
        "mobilizer_login.create": {
            "campaign": str(world.campaign.id),
            "ward": str(world.other_ward.id),
            "role": "mobilizer",
            "username": "wanjiku",
            "first_name": "Wanjiku",
            "last_name": "Njeri",
        },
    }
    headers = (
        admin_headers
        if actor == "root"
        else world.headers({"jane": "candidate", "amina": "manager"}[actor])
    )

    response = await getattr(client, method)(
        f"/api{path.format(**ids)}",
        headers=headers,
        **({"json": bodies[action]} if action in bodies else {}),
    )

    assert response.status_code < 300, response.text
    written = list(await session.scalars(select(AuditEvent).where(AuditEvent.action == action)))
    assert [(e.subject_type, e.actor_name) for e in written] == [(subject_type, actor)]


async def test_the_audit_trail_pages_newest_first_with_limit_and_offset(
    client: httpx.AsyncClient, session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    for n in range(5):
        record(session, actor=None, action=f"campaign.step{n}", subject_type="campaign")
    await session.commit()

    every = (await client.get("/api/admin/audit/", headers=admin_headers)).json()
    pages = [
        (await client.get(f"/api/admin/audit/?limit=2&offset={offset}", headers=admin_headers))
        for offset in (0, 2, 5)
    ]

    assert len(every) == 5
    assert [p.json() for p in pages] == [every[:2], every[2:4], []]
