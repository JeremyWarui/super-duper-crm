"""The admin console, and the flag that is the only way into it."""

import re
import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuthToken,
    Campaign,
    CampaignMember,
    Event,
    Mobilizer,
    Supporter,
    Target,
    User,
    UserRole,
)
from tests.conftest import World
from tests.factories import TEST_PASSWORD, auth, fresh_password, make_user, sign_in


def _admin_gets() -> list[str]:
    """Every admin GET the app serves, with a sample id for the ones that take one.

    Read off the app rather than listed, so a route added later is guarded by
    these tests without anybody remembering to add it here.
    """
    from backend.main import app

    sample = "00000000-0000-0000-0000-000000000001"
    return sorted(
        re.sub(r"\{[^}]+\}", sample, path)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/api/admin/") and "get" in methods
    )


READS = _admin_gets()


async def _admin(session: AsyncSession, client: httpx.AsyncClient) -> dict[str, str]:
    root = await make_user(session, username="root", role=UserRole.MANAGER)
    root.is_superuser = True
    await session.commit()
    return auth(await sign_in(client, "root"))


# ------------------------------------------------------------------ the gate


@pytest.mark.parametrize("path", READS)
async def test_the_admin_console_needs_a_token(client: httpx.AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 401


@pytest.mark.parametrize("path", READS)
@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_no_campaign_role_reaches_the_admin_console(
    client: httpx.AsyncClient, world: World, path: str, role: str
) -> None:
    """A manager runs a campaign. That is not the same as running the deployment."""
    response = await client.get(path, headers=world.headers(role))

    assert response.status_code == 403
    assert response.json()["detail"] == "This is not yours to see."


async def test_the_admin_writes_are_shut_to_a_manager_too(
    client: httpx.AsyncClient, world: World
) -> None:
    head = world.headers("manager")
    victim = str(world.candidate.id)

    assert (
        await client.post(f"/api/admin/users/{victim}/reset-password/", headers=head, json={})
    ).status_code == 403
    assert (
        await client.post(
            f"/api/admin/users/{victim}/active/", headers=head, json={"active": False}
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/admin/campaigns/{world.campaign.id}/members/",
            headers=head,
            json={"user": victim, "role": "manager"},
        )
    ).status_code == 403
    assert (
        await client.delete(
            f"/api/admin/campaigns/{world.campaign.id}/members/{victim}/", headers=head
        )
    ).status_code == 403
    assert (
        await client.delete(f"/api/admin/campaigns/{world.campaign.id}/", headers=head)
    ).status_code == 403


async def test_signing_up_cannot_make_a_superuser(
    client: httpx.AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sign-up body forbids unknown fields, so the flag cannot even be asked for."""
    from backend.config import get_settings

    monkeypatch.setenv("ALLOW_REGISTRATION", "true")
    get_settings.cache_clear()
    try:
        reply = await client.post(
            "/api/auth/register/",
            json={
                "username": "sneaky",
                "password": TEST_PASSWORD,
                "role": "manager",
                "is_superuser": True,
            },
        )
    finally:
        get_settings.cache_clear()

    assert reply.status_code == 400
    assert (
        await session.execute(select(User).where(User.username == "sneaky"))
    ).scalar_one_or_none() is None


# -------------------------------------------------------------------- reads


async def test_the_overview_counts_everything_and_lists_every_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    body = (await client.get("/api/admin/overview/", headers=head)).json()

    assert body["totals"]["campaigns"] == 1
    assert body["totals"]["members"] == 3
    assert body["totals"]["targets"] == 2
    assert [c["title"] for c in body["campaigns"]] == ["Jane for Roysambu"]
    team = body["campaigns"][0]
    assert {m["username"]: m["role"] for m in team["members"]} == {
        "jane": "candidate",
        "amina": "manager",
        "juma": "mobilizer",
    }
    assert team["candidate"] == "jane"
    assert team["targets"] == 2  # Zimmerman and Githurai


async def test_the_admin_sees_campaigns_no_manager_is_on(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The point of the console: a campaign with nobody on it is still visible."""
    await session.execute(
        CampaignMember.__table__.delete().where(CampaignMember.campaign_id == world.campaign.id)
    )
    await session.commit()
    head = await _admin(session, client)

    body = (await client.get("/api/admin/campaigns/", headers=head)).json()

    assert [c["title"] for c in body] == ["Jane for Roysambu"]
    assert body[0]["members"] == []
    assert (await client.get("/api/campaigns/", headers=world.headers("manager"))).json() == []


async def test_the_user_list_names_every_login_and_where_it_reaches(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    body = (await client.get("/api/admin/users/", headers=head)).json()

    by_name = {u["username"]: u for u in body}
    assert sorted(by_name) == ["amina", "jane", "juma", "root"]
    assert [c[1] for c in by_name["amina"]["campaigns"]] == ["Jane for Roysambu"]
    assert by_name["root"]["campaigns"] == []
    assert all("password" not in u and "password_hash" not in u for u in body)


async def test_the_user_list_filters_by_role_and_by_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    managers = (await client.get("/api/admin/users/?role=manager", headers=head)).json()
    assert sorted(u["username"] for u in managers) == ["amina", "root"]

    on_it = (
        await client.get(f"/api/admin/users/?campaign={world.campaign.id}", headers=head)
    ).json()
    assert sorted(u["username"] for u in on_it) == ["amina", "jane", "juma"]


async def test_one_campaign_reads_back_with_its_numbers(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    body = (await client.get(f"/api/admin/campaigns/{world.campaign.id}/", headers=head)).json()

    assert body["title"] == "Jane for Roysambu"
    assert body["mobilizers"] == 1
    assert body["votes_needed"] > 0


async def test_an_unknown_campaign_is_a_404(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    unknown = uuid.uuid4()

    assert (await client.get(f"/api/admin/campaigns/{unknown}/", headers=head)).status_code == 404


# ------------------------------------------------------------------- writes


async def test_a_reset_hands_back_a_working_password_and_signs_the_old_session_out(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The only recovery from a password that was shown once and lost."""
    head = await _admin(session, client)
    before = world.headers("candidate")
    assert (await client.get("/api/campaigns/", headers=before)).status_code == 200

    reply = await client.post(
        f"/api/admin/users/{world.candidate.id}/reset-password/", headers=head, json={}
    )

    assert reply.status_code == 200
    assert reply.json()["username"] == "jane"
    fresh = reply.json()["password"]
    assert len(fresh) >= 12

    assert (await client.get("/api/campaigns/", headers=before)).status_code == 401
    token = await sign_in(client, "jane", fresh)
    assert (await client.get("/api/campaigns/", headers=auth(token))).status_code == 200


async def test_a_reset_can_be_given_a_chosen_password(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    chosen = fresh_password()

    reply = await client.post(
        f"/api/admin/users/{world.candidate.id}/reset-password/",
        headers=head,
        json={"password": chosen},
    )

    assert reply.json()["password"] == chosen
    assert await sign_in(client, "jane", chosen)


async def test_a_short_chosen_password_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    reply = await client.post(
        f"/api/admin/users/{world.candidate.id}/reset-password/",
        headers=head,
        json={"password": fresh_password()[:5]},
    )

    assert reply.status_code == 400


async def test_resetting_an_unknown_login_says_so(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    reply = await client.post(
        f"/api/admin/users/{uuid.uuid4()}/reset-password/", headers=head, json={}
    )

    assert reply.status_code == 404
    assert reply.json()["detail"] == "No such user."


async def test_disabling_a_login_stops_it_at_once(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    theirs = world.headers("mobilizer")
    assert (await client.get("/api/campaigns/", headers=theirs)).status_code == 200

    reply = await client.post(
        f"/api/admin/users/{world.mobilizer_user.id}/active/", headers=head, json={"active": False}
    )

    assert reply.status_code == 200
    assert reply.json()["is_active"] is False
    assert (await client.get("/api/campaigns/", headers=theirs)).status_code == 401
    assert (
        await session.scalar(select(AuthToken).where(AuthToken.user_id == world.mobilizer_user.id))
    ) is None


async def test_a_disabled_login_cannot_sign_back_in_until_it_is_enabled(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    from tests.factories import TEST_PASSWORD

    await client.post(
        f"/api/admin/users/{world.mobilizer_user.id}/active/", headers=head, json={"active": False}
    )
    refused = await client.post(
        "/api/auth/login/", json={"username": "juma", "password": TEST_PASSWORD}
    )
    assert refused.status_code == 400

    await client.post(
        f"/api/admin/users/{world.mobilizer_user.id}/active/", headers=head, json={"active": True}
    )
    assert await sign_in(client, "juma")


@pytest.mark.parametrize("who", ["candidate", "manager"])
async def test_an_admin_disables_the_logins_a_campaign_cannot_remove(
    client: httpx.AsyncClient, session: AsyncSession, world: World, who: str
) -> None:
    head = await _admin(session, client)
    target = getattr(world, who)
    theirs = world.headers(who)

    reply = await client.post(
        f"/api/admin/users/{target.id}/active/", headers=head, json={"active": False}
    )

    assert reply.status_code == 200, reply.text
    assert reply.json()["is_active"] is False
    assert (await client.get("/api/campaigns/", headers=theirs)).status_code == 401


async def test_the_console_disables_a_login_and_never_deletes_one(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    reply = await client.delete(f"/api/admin/users/{world.manager.id}/", headers=head)

    assert reply.status_code in (404, 405)
    assert await session.get(User, world.manager.id) is not None


async def test_an_admin_cannot_disable_themselves(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    me = (await client.get("/api/admin/users/?role=manager", headers=head)).json()
    root = next(u for u in me if u["username"] == "root")

    reply = await client.post(
        f"/api/admin/users/{root['id']}/active/", headers=head, json={"active": False}
    )

    assert reply.status_code == 400
    assert (await client.get("/api/admin/overview/", headers=head)).status_code == 200


async def test_putting_somebody_on_a_campaign_gives_them_the_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    outsider = await make_user(session, username="rescue", role=UserRole.MANAGER)
    token = await sign_in(client, "rescue")
    assert (await client.get("/api/campaigns/", headers=auth(token))).json() == []

    reply = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=head,
        json={"user": str(outsider.id)},
    )

    assert reply.status_code == 201
    assert "rescue" in {m["username"] for m in reply.json()["members"]}
    assert [c["id"] for c in (await client.get("/api/campaigns/", headers=auth(token))).json()] == [
        str(world.campaign.id)
    ]


async def test_adding_somebody_twice_leaves_one_place_not_two(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    reply = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=head,
        json={"user": str(world.mobilizer_user.id)},
    )
    assert reply.status_code == 201
    body = (await client.get(f"/api/admin/campaigns/{world.campaign.id}/", headers=head)).json()

    places = [m for m in body["members"] if m["username"] == "juma"]
    assert len(places) == 1
    # Their own login says mobilizer, and no payload can say otherwise.
    assert places[0]["role"] == "mobilizer"


async def test_the_place_somebody_takes_is_their_login_s_role_and_cannot_be_asked_for(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """A membership naming a capacity the login does not have would be a lie.

    Every permission check reads `users.role`, so a row saying "mobilizer" for a
    manager would hand them a campaign-deleting manager's powers under a name
    that reads harmless.
    """
    head = await _admin(session, client)
    outsider = await make_user(session, username="rescue", role=UserRole.MANAGER)
    await session.commit()

    refused = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=head,
        json={"user": str(outsider.id), "role": "mobilizer"},
    )

    assert refused.status_code == 400
    accepted = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=head,
        json={"user": str(outsider.id)},
    )
    assert accepted.status_code == 201
    assert [m["role"] for m in accepted.json()["members"] if m["username"] == "rescue"] == [
        "manager"
    ]


async def test_a_superuser_is_not_put_on_a_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The console reads every campaign already, and the campaign app would not."""
    head = await _admin(session, client)
    root = await session.scalar(select(User).where(User.is_superuser.is_(True)))

    refused = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=head,
        json={"user": str(root.id)},
    )

    assert refused.status_code == 400
    assert "superuser" in refused.json()["detail"]


async def test_a_disabled_login_is_not_put_on_a_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    outsider = await make_user(session, username="rescue", role=UserRole.MANAGER)
    outsider.is_active = False
    await session.commit()

    refused = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=head,
        json={"user": str(outsider.id)},
    )

    assert refused.status_code == 400
    assert "disabled" in refused.json()["detail"]


async def test_a_campaign_manager_cannot_delete_the_login_that_runs_the_deployment(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Deleting the last superuser leaves nobody able to reach the console."""
    await _admin(session, client)
    root = await session.scalar(select(User).where(User.is_superuser.is_(True)))
    # Written straight in: no route puts a superuser on a campaign any more, but
    # a database migrated from before that rule can still hold such a row.
    session.add(CampaignMember(campaign_id=world.campaign.id, user_id=root.id, role=root.role))
    await session.commit()

    refused = await client.delete(f"/api/users/{root.id}/", headers=world.headers("manager"))

    assert refused.status_code == 403
    assert await session.get(User, root.id) is not None


async def test_taking_somebody_off_a_campaign_takes_it_away_from_them(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    theirs = world.headers("manager")
    assert (await client.get("/api/campaigns/", headers=theirs)).json() != []

    reply = await client.delete(
        f"/api/admin/campaigns/{world.campaign.id}/members/{world.manager.id}/", headers=head
    )

    assert reply.status_code == 204
    assert (await client.get("/api/campaigns/", headers=theirs)).json() == []


async def test_an_admin_deletes_a_campaign_and_everything_on_it_but_the_logins(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    manager = world.headers("manager")
    event = await client.post(
        "/api/events/",
        headers=manager,
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "title": "Zimmerman town hall",
            "venue": "Social hall",
            "scheduled_date": "2027-06-12",
            "status": "planned",
            "mobilizer": str(world.mobilizer.id),
        },
    )
    assert event.status_code == 201, event.text
    supporter = await client.post(
        "/api/supporters/",
        headers=world.headers("mobilizer"),
        json={
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
            "full_name": "Wanjiku Njeri",
            "phone": "+254700333444",
            "consent_given": True,
        },
    )
    assert supporter.status_code == 201, supporter.text
    head = await _admin(session, client)

    reply = await client.delete(f"/api/admin/campaigns/{world.campaign.id}/", headers=head)

    assert reply.status_code == 204
    session.expire_all()
    assert await session.get(Campaign, world.campaign.id) is None
    for table in (CampaignMember, Target, Mobilizer, Event, Supporter):
        assert await session.scalar(select(func.count()).select_from(table)) == 0, table
    for who in ("candidate", "manager", "mobilizer"):
        assert (await client.get("/api/campaigns/", headers=world.headers(who))).json() == []
    assert await session.get(User, world.candidate.id) is not None
    overview = (await client.get("/api/admin/overview/", headers=head)).json()
    assert overview["campaigns"] == []


async def test_deleting_a_campaign_that_is_not_there_is_a_404(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    reply = await client.delete(f"/api/admin/campaigns/{uuid.uuid4()}/", headers=head)

    assert reply.status_code == 404
    assert reply.json()["detail"] == "No such campaign."


async def test_the_candidate_cannot_be_taken_off_their_own_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    reply = await client.delete(
        f"/api/admin/campaigns/{world.campaign.id}/members/{world.candidate.id}/", headers=head
    )

    assert reply.status_code == 400
    assert "delete the campaign instead" in reply.json()["detail"]


async def test_taking_off_somebody_who_is_not_on_it_says_so(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    outsider = await make_user(session, username="stranger", role=UserRole.MANAGER)

    reply = await client.delete(
        f"/api/admin/campaigns/{world.campaign.id}/members/{outsider.id}/", headers=head
    )

    assert reply.status_code == 400
    assert reply.json()["detail"] == "They are not on that campaign."


async def test_the_console_never_widens_what_a_manager_sees(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """An admin reading everything must leave the scoped routes exactly as they were."""
    head = await _admin(session, client)
    await make_user(session, username="rival", role=UserRole.MANAGER)
    rival = auth(await sign_in(client, "rival"))

    assert len((await client.get("/api/admin/campaigns/", headers=head)).json()) == 1

    assert (await client.get("/api/campaigns/", headers=rival)).json() == []
    # On no campaign, a manager sees themselves and nobody else.
    assert [u["username"] for u in (await client.get("/api/users/", headers=rival)).json()] == [
        "rival"
    ]
    assert (
        await client.get(f"/api/campaigns/{world.campaign.id}/", headers=rival)
    ).status_code == 404


async def test_one_superuser_can_be_shut_off_when_another_is_left(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """A compromised admin account has to be stoppable."""
    head = await _admin(session, client)
    spare = await make_user(session, username="spare_root", role=UserRole.MANAGER)
    spare.is_superuser = True
    await session.commit()

    reply = await client.post(
        f"/api/admin/users/{spare.id}/active/", headers=head, json={"active": False}
    )

    assert reply.status_code == 200
    assert reply.json()["is_active"] is False


# ------------------------------------------------------- creating a login


async def test_the_console_creates_a_manager_and_puts_them_on_a_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    made = await client.post(
        "/api/admin/users/",
        headers=head,
        json={
            "username": "newmgr",
            "role": "manager",
            "first_name": "New",
            "last_name": "Manager",
            "campaign": str(world.campaign.id),
        },
    )

    assert made.status_code == 201, made.text
    body = made.json()
    assert body["role"] == "manager"
    assert body["password"]

    # The password is usable, and they land on the campaign rather than setup.
    signed_in = await client.post(
        "/api/auth/login/", json={"username": "newmgr", "password": body["password"]}
    )
    assert signed_in.status_code == 200, signed_in.text
    seen = await client.get("/api/campaigns/", headers=auth(signed_in.json()["token"]))
    assert [c["id"] for c in seen.json()] == [str(world.campaign.id)]


async def test_the_console_creates_an_aspirant_with_no_campaign_yet(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """An aspirant gets a campaign when one is set up for them, not before."""
    head = await _admin(session, client)

    made = await client.post(
        "/api/admin/users/",
        headers=head,
        json={"username": "newaspirant", "role": "candidate"},
    )

    assert made.status_code == 201, made.text
    signed_in = await client.post(
        "/api/auth/login/",
        json={"username": "newaspirant", "password": made.json()["password"]},
    )
    assert signed_in.status_code == 200
    assert (
        await client.get("/api/campaigns/", headers=auth(signed_in.json()["token"]))
    ).json() == []


async def test_an_aspirant_cannot_be_added_to_a_campaign_that_has_one(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """A campaign is for one candidate; a second is refused, not quietly added."""
    head = await _admin(session, client)

    refused = await client.post(
        "/api/admin/users/",
        headers=head,
        json={
            "username": "second",
            "role": "candidate",
            "campaign": str(world.campaign.id),
        },
    )

    assert refused.status_code == 400
    assert "already" in refused.json()["detail"]
    assert await session.scalar(select(User).where(User.username == "second")) is None


async def test_that_refusal_does_not_depend_on_a_warm_session(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The reason names the sitting candidate, and must not lazy-load to find them.

    Every other test shares a session that already holds the candidate, so a
    lazy `campaign.candidate` resolves from the identity map and the refusal
    looks fine. On a fresh connection it is IO in the wrong place, and the
    caller gets a 500 instead of the reason.
    """
    head = await _admin(session, client)
    campaign_id = world.campaign.id
    session.expunge_all()

    refused = await client.post(
        "/api/admin/users/",
        headers=head,
        json={"username": "second", "role": "candidate", "campaign": str(campaign_id)},
    )

    assert refused.status_code == 400, refused.text
    assert "jane" in refused.json()["detail"]


async def test_an_existing_aspirant_cannot_be_put_on_a_campaign_that_has_one(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    peter = await make_user(session, username="peter", role=UserRole.CANDIDATE)

    refused = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=head,
        json={"user": str(peter.id)},
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["detail"] == (
        "peter is a candidate, and that campaign already has its candidate."
    )
    rows = await session.scalars(
        select(CampaignMember.user_id).where(
            CampaignMember.campaign_id == world.campaign.id,
            CampaignMember.role == UserRole.CANDIDATE,
        )
    )
    assert list(rows) == [world.candidate.id]


async def test_a_mobilizer_made_here_gets_the_ward_that_scopes_them(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    made = await client.post(
        "/api/admin/users/",
        headers=head,
        json={
            "username": "newboots",
            "role": "mobilizer",
            "campaign": str(world.campaign.id),
            "ward": str(world.ward.id),
        },
    )

    assert made.status_code == 201, made.text
    signed_in = await client.post(
        "/api/auth/login/",
        json={"username": "newboots", "password": made.json()["password"]},
    )
    token = auth(signed_in.json()["token"])
    assert [c["id"] for c in (await client.get("/api/campaigns/", headers=token)).json()] == [
        str(world.campaign.id)
    ]
    # Scoped to their ward, which is what the Mobilizer row is for.
    events = await client.get("/api/events/", headers=token)
    assert events.status_code == 200


async def test_a_mobilizer_without_a_ward_is_refused_rather_than_left_blind(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    refused = await client.post(
        "/api/admin/users/",
        headers=head,
        json={
            "username": "blind",
            "role": "mobilizer",
            "campaign": str(world.campaign.id),
        },
    )

    assert refused.status_code == 400
    assert "ward" in refused.json()["detail"]
    assert await session.scalar(select(User).where(User.username == "blind")) is None


async def test_a_mobilizer_with_no_campaign_at_all_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    refused = await client.post(
        "/api/admin/users/", headers=head, json={"username": "loose", "role": "mobilizer"}
    )

    assert refused.status_code == 400


async def test_a_username_already_taken_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    refused = await client.post(
        "/api/admin/users/", headers=head, json={"username": "amina", "role": "manager"}
    )

    assert refused.status_code == 400
    assert "taken" in refused.json()["detail"]


async def test_a_login_made_here_cannot_ask_to_run_the_deployment(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    refused = await client.post(
        "/api/admin/users/",
        headers=head,
        json={"username": "sneaky", "role": "manager", "is_superuser": True},
    )

    assert refused.status_code == 400
    assert await session.scalar(select(User).where(User.username == "sneaky")) is None


async def test_no_campaign_role_may_create_a_login_here(
    client: httpx.AsyncClient, world: World
) -> None:
    for role in ("candidate", "manager", "mobilizer"):
        refused = await client.post(
            "/api/admin/users/",
            headers=world.headers(role),
            json={"username": f"by{role}", "role": "manager"},
        )
        assert refused.status_code == 403, role


async def test_the_console_lists_the_wards_a_campaign_works(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The mobilizer ward picker reads these, so they have to be there."""
    head = await _admin(session, client)

    body = (await client.get("/api/admin/overview/", headers=head)).json()

    wards = body["campaigns"][0]["wards"]
    assert wards, "a campaign with targets must report its wards"
    assert {w["name"] for w in wards} >= {world.ward.name}


# --------------------------------------------------------- renaming a campaign


async def test_the_console_renames_a_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    renamed = await client.patch(
        f"/api/admin/campaigns/{world.campaign.id}/",
        headers=head,
        json={"title": "Jane for Roysambu 2027"},
    )

    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Jane for Roysambu 2027"


async def test_the_new_name_is_what_the_campaign_team_then_sees(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """A rename nobody on the campaign can see would be a rename in name only."""
    head = await _admin(session, client)

    await client.patch(
        f"/api/admin/campaigns/{world.campaign.id}/",
        headers=head,
        json={"title": "Jane for Roysambu 2027"},
    )

    seen = await client.get("/api/campaigns/", headers=world.headers("manager"))
    assert [c["title"] for c in seen.json()] == ["Jane for Roysambu 2027"]


async def test_renaming_moves_nothing_but_the_name(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)
    before = (await client.get(f"/api/admin/campaigns/{world.campaign.id}/", headers=head)).json()

    after = (
        await client.patch(
            f"/api/admin/campaigns/{world.campaign.id}/",
            headers=head,
            json={"title": "Something Else Entirely"},
        )
    ).json()

    assert after["candidate"] == before["candidate"]
    assert after["targets"] == before["targets"]
    assert {m["username"] for m in after["members"]} == {m["username"] for m in before["members"]}


async def test_a_campaign_cannot_be_renamed_to_nothing(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    refused = await client.patch(
        f"/api/admin/campaigns/{world.campaign.id}/", headers=head, json={"title": "   "}
    )

    assert refused.status_code == 400
    kept = await client.get(f"/api/admin/campaigns/{world.campaign.id}/", headers=head)
    assert kept.json()["title"] == world.campaign.title


async def test_no_campaign_role_may_rename_a_campaign(
    client: httpx.AsyncClient, world: World
) -> None:
    for role in ("candidate", "manager", "mobilizer"):
        refused = await client.patch(
            f"/api/admin/campaigns/{world.campaign.id}/",
            headers=world.headers(role),
            json={"title": "Mine Now"},
        )
        assert refused.status_code == 403, role


async def test_renaming_a_campaign_that_is_not_there_says_so(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    refused = await client.patch(
        f"/api/admin/campaigns/{uuid.uuid4()}/", headers=head, json={"title": "Ghost"}
    )

    assert refused.status_code == 404


# ------------------------------------------- what the campaign team is told


async def test_everyone_on_a_campaign_is_told_whose_it_is_and_which_seat(
    client: httpx.AsyncClient, world: World
) -> None:
    """Name, candidate and seat, without a second request to resolve an id."""
    for role in ("candidate", "manager", "mobilizer"):
        seen = (await client.get("/api/campaigns/", headers=world.headers(role))).json()
        assert len(seen) == 1, role
        campaign = seen[0]
        assert campaign["title"] == world.campaign.title, role
        assert campaign["candidate_username"] == "jane", role
        assert campaign["candidate_name"], role
        assert "MP" in campaign["seat"], role
        assert campaign["area_name"], role


async def test_the_campaign_names_itself_on_a_cold_session(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The candidate and the area are relationships; reading them must not lazy-load."""
    token = world.headers("manager")
    session.expunge_all()

    seen = await client.get("/api/campaigns/", headers=token)

    assert seen.status_code == 200, seen.text
    assert seen.json()[0]["candidate_username"] == "jane"
    assert seen.json()[0]["area_name"]


async def test_a_disabled_login_is_not_handed_a_password_it_cannot_use(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Resetting a disabled login hands out a password that signs nobody in."""
    head = await _admin(session, client)
    amina = await session.scalar(select(User).where(User.username == "amina"))
    await client.post(f"/api/admin/users/{amina.id}/active/", headers=head, json={"active": False})

    refused = await client.post(
        f"/api/admin/users/{amina.id}/reset-password/", headers=head, json={}
    )

    assert refused.status_code == 400
    assert "disabled" in refused.json()["detail"]


async def test_a_mobilizer_cannot_be_given_a_ward_the_campaign_does_not_work(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Their supporters and events would land where the campaign has no target."""
    from backend.models import Constituency, Ward

    head = await _admin(session, client)
    # A ward in another constituency, so no target of this campaign covers it.
    elsewhere = Constituency(county_id=world.county.id, name="Westlands", code="280")
    theirs = Ward(constituency=elsewhere, name="Parklands", code="1400", registered_voters=20_000)
    session.add_all([elsewhere, theirs])
    await session.commit()

    refused = await client.post(
        "/api/admin/users/",
        headers=head,
        json={
            "username": "stranded",
            "role": "mobilizer",
            "campaign": str(world.campaign.id),
            "ward": str(theirs.id),
        },
    )

    assert refused.status_code == 400
    assert "not a ward" in refused.json()["detail"]
    assert await session.scalar(select(User).where(User.username == "stranded")) is None


async def test_a_username_that_appears_between_the_check_and_the_insert_is_refused(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check is advisory; the unique constraint rules, and says so politely."""
    from backend.services import admin as service

    head = await _admin(session, client)
    await make_user(session, username="racer", role=UserRole.MANAGER)
    await session.commit()

    # Blind the pre-check, which is what a concurrent create does by winning
    # the gap between the lookup and the insert.
    async def _missed(_session, _username):
        return False

    monkeypatch.setattr(service, "_username_taken", _missed)

    refused = await client.post(
        "/api/admin/users/", headers=head, json={"username": "racer", "role": "manager"}
    )

    assert refused.status_code == 400
    assert "taken" in refused.json()["detail"]


# --------------------------------------------- not there, versus not allowed


async def test_a_login_that_is_not_there_cannot_be_disabled(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    reply = await client.post(
        f"/api/admin/users/{uuid.uuid4()}/active/", headers=head, json={"active": False}
    )

    assert reply.status_code == 404
    assert reply.json()["detail"] == "No such user."


async def test_a_campaign_that_is_not_there_cannot_gain_a_member(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    reply = await client.post(
        f"/api/admin/campaigns/{uuid.uuid4()}/members/",
        headers=head,
        json={"user": str(world.manager.id)},
    )

    assert reply.status_code == 404
    assert reply.json()["detail"] == "No such campaign."


async def test_a_campaign_that_is_not_there_cannot_lose_a_member(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    head = await _admin(session, client)

    reply = await client.delete(
        f"/api/admin/campaigns/{uuid.uuid4()}/members/{world.manager.id}/", headers=head
    )

    assert reply.status_code == 404
    assert reply.json()["detail"] == "No such campaign."


async def test_an_unknown_login_in_the_body_is_a_bad_request_not_a_missing_page(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The path names a real campaign; only the body is wrong."""
    head = await _admin(session, client)

    reply = await client.post(
        f"/api/admin/campaigns/{world.campaign.id}/members/",
        headers=head,
        json={"user": str(uuid.uuid4())},
    )

    assert reply.status_code == 400
    assert reply.json()["detail"] == "No such user."
