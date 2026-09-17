"""Reading campaigns, setting one up, and rebuilding its targets."""

import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Campaign, CampaignMember, Target, User, UserRole, Ward
from backend.services.accounts import add_member
from backend.services.errors import Refused
from tests.conftest import World
from tests.factories import (
    auth,
    fresh_password,
    make_rival_campaign,
    make_user,
    members_of,
    sign_in,
)


def _setup_body(world: World, **overrides) -> dict:
    body = {
        "title": "Peter for Kasarani",
        "office_level": "constituency",
        "constituency": str(world.constituency.id),
    }
    return {**body, **overrides}


async def test_listing_campaigns_needs_a_token(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/campaigns/")).status_code == 401


async def test_a_campaign_carries_the_fields_the_dashboard_reads(
    client: httpx.AsyncClient, world: World
) -> None:
    body = (await client.get("/api/campaigns/", headers=world.headers("manager"))).json()

    assert len(body) == 1
    assert body[0]["id"] == str(world.campaign.id)
    assert body[0]["title"] == "Jane for Roysambu"
    assert body[0]["office_level"] == "constituency"
    assert body[0]["constituency"] == str(world.constituency.id)
    assert body[0]["ward"] is None
    assert body[0]["operational_grain"] == "ward"


@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_everyone_on_a_campaign_sees_it_and_not_a_rival_s(
    client: httpx.AsyncClient, session: AsyncSession, world: World, role: str
) -> None:
    rival = await make_rival_campaign(session, world.other_ward)

    body = (await client.get("/api/campaigns/", headers=world.headers(role))).json()
    other = await client.get(f"/api/campaigns/{rival.id}/", headers=world.headers(role))

    assert [c["title"] for c in body] == ["Jane for Roysambu"]
    assert other.status_code == 404


async def test_every_manager_on_a_campaign_works_it_whatever_their_username(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    second = await make_user(session, username="otieno", role=UserRole.MANAGER)
    await add_member(session, world.campaign.id, second)
    await session.commit()

    for username in ("amina", "otieno"):
        head = auth(await sign_in(client, username))
        seen = [c["id"] for c in (await client.get("/api/campaigns/", headers=head)).json()]
        assigned = await client.post(
            "/api/mobilizers/",
            headers=head,
            json={
                "campaign": str(world.campaign.id),
                "ward": str(world.other_ward.id),
                "full_name": f"Organizer for {username}",
            },
        )

        assert seen == [str(world.campaign.id)]
        assert assigned.status_code == 201, assigned.text


@pytest.mark.parametrize("role", [UserRole.MANAGER, UserRole.MOBILIZER])
async def test_a_login_on_no_campaign_sees_none(
    client: httpx.AsyncClient, session: AsyncSession, world: World, role: UserRole
) -> None:
    await make_user(session, username="loose", role=role)
    head = auth(await sign_in(client, "loose"))

    assert (await client.get("/api/campaigns/", headers=head)).json() == []
    assert (
        await client.get(f"/api/campaigns/{world.campaign.id}/", headers=head)
    ).status_code == 404


async def test_a_manager_sets_a_campaign_up_with_its_targets_and_a_new_aspirant(
    client: httpx.AsyncClient, session: AsyncSession, world: World, new_manager: dict
) -> None:
    """Zimmerman 30,701 and Githurai 35,899 at 60% turnout: 9,211 + 10,770."""
    response = await client.post(
        "/api/campaigns/setup/",
        headers=new_manager,
        json=_setup_body(
            world,
            election_date="2027-08-10",
            new_candidate={"username": "peter", "first_name": "Peter", "last_name": "Kimani"},
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["election_date"] == "2027-08-10"
    assert body["setup"] == {
        "grain": "ward",
        "units": 2,
        "total_registered": 66_600,
        "win_number": 19_981,
        "note": None,
    }
    campaign_id = uuid.UUID(body["id"])
    assert (
        await session.scalar(
            select(func.count()).select_from(Target).where(Target.campaign_id == campaign_id)
        )
        == 2
    )
    assert await members_of(session, campaign_id) == {"peter": "candidate", "newmanager": "manager"}

    login = body["candidate_login"]
    assert login["username"] == "peter"
    assert len(login["password"]) >= 12
    assert body["candidate"] == login["id"]
    for head in (new_manager, auth(await sign_in(client, "peter", login["password"]))):
        listed = (await client.get("/api/campaigns/", headers=head)).json()
        assert [c["title"] for c in listed] == ["Peter for Kasarani"]


async def test_a_candidate_sets_their_own_campaign_up_alone(
    client: httpx.AsyncClient, session: AsyncSession, world: World, new_candidate: dict
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=new_candidate,
        json={
            "title": "Peter for Governor",
            "office_level": "county",
            "county": str(world.county.id),
        },
    )

    assert response.status_code == 201, response.text
    mine = await session.scalar(select(User.id).where(User.username == "newaspirant"))
    assert response.json()["candidate"] == str(mine)
    assert await members_of(session, uuid.UUID(response.json()["id"])) == {
        "newaspirant": "candidate"
    }


async def test_the_default_password_reaches_the_aspirant_created_at_setup(
    client: httpx.AsyncClient,
    world: World,
    new_manager: dict,
    monkeypatch: pytest.MonkeyPatch,
    fresh_settings: None,
) -> None:
    shared = fresh_password()
    monkeypatch.setenv("DEFAULT_USER_PASSWORD", shared)

    response = await client.post(
        "/api/campaigns/setup/",
        headers=new_manager,
        json=_setup_body(world, new_candidate={"username": "peter"}),
    )

    assert response.status_code == 201
    assert response.json()["candidate_login"]["password"] == shared


async def test_a_mobilizer_may_not_set_a_campaign_up(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/", headers=world.headers("mobilizer"), json=_setup_body(world)
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({}, "Say who this campaign is for"),
        ({"new_candidate": {"username": "jane"}}, "The username jane is already taken."),
        (
            {"constituency": None, "new_candidate": {"username": "peter"}},
            "A Constituency (MP) campaign needs its constituency set.",
        ),
        ({"candidate": "00000000-0000-0000-0000-000000000001"}, "candidate"),
        ({"office_level": "president"}, "office_level"),
    ],
)
async def test_a_setup_the_server_cannot_make_is_refused_and_makes_nothing(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    new_manager: dict,
    overrides: dict,
    message: str,
) -> None:
    response = await client.post(
        "/api/campaigns/setup/", headers=new_manager, json=_setup_body(world, **overrides)
    )

    assert response.status_code == 400
    assert message in response.json()["detail"]
    assert await session.scalar(select(func.count()).select_from(Campaign)) == 1


async def test_a_candidate_cannot_create_another_candidate(
    client: httpx.AsyncClient, world: World, new_candidate: dict
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=new_candidate,
        json=_setup_body(world, new_candidate={"username": "peter"}),
    )
    assert response.status_code == 400
    assert "do not create another" in response.json()["detail"]


async def test_an_mca_campaign_with_no_centres_says_so_in_the_summary(
    client: httpx.AsyncClient, world: World, new_manager: dict
) -> None:
    body = (
        await client.post(
            "/api/campaigns/setup/",
            headers=new_manager,
            json={
                "title": "Amina for Githurai",
                "office_level": "ward",
                "ward": str(world.other_ward.id),
                "new_candidate": {"username": "peter"},
            },
        )
    ).json()

    assert body["setup"]["grain"] == "centre"
    assert body["setup"]["units"] == 0
    assert "Githurai" in body["setup"]["note"]


@pytest.mark.parametrize("role", ["manager", "candidate"])
async def test_nobody_already_on_a_campaign_sets_up_another(
    client: httpx.AsyncClient, session: AsyncSession, world: World, role: str
) -> None:
    body = {"title": "A second one", "office_level": "ward", "ward": str(world.other_ward.id)}
    if role == "manager":
        body["new_candidate"] = {"username": "peter"}

    reply = await client.post("/api/campaigns/setup/", headers=world.headers(role), json=body)

    assert reply.status_code == 400
    assert reply.json()["detail"] == (
        "You are already on Jane for Roysambu; a login belongs to one campaign."
    )
    assert list(await session.scalars(select(Campaign.title))) == ["Jane for Roysambu"]
    assert await session.scalar(select(User.id).where(User.username == "peter")) is None


async def test_nobody_already_on_a_campaign_is_put_on_another(
    session: AsyncSession, world: World
) -> None:
    other = await make_rival_campaign(session, world.other_ward)

    for person in (world.candidate, world.manager, world.mobilizer_user):
        with pytest.raises(Refused) as refused:
            await add_member(session, other.id, person)
        assert str(refused.value) == (
            f"{person.username} is already on Jane for Roysambu; a login belongs to one campaign."
        )


async def test_adding_somebody_already_on_the_campaign_leaves_one_place(
    session: AsyncSession, world: World
) -> None:
    await add_member(session, world.campaign.id, world.candidate)
    await session.commit()

    assert (
        await session.scalar(
            select(func.count())
            .select_from(CampaignMember)
            .where(CampaignMember.user_id == world.candidate.id)
        )
        == 1
    )


async def test_a_setup_that_races_past_the_check_still_answers_with_the_rule(
    client: httpx.AsyncClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both concurrent requests pass the check; the database index decides."""
    from backend.api.routers import campaigns
    from backend.services import accounts

    async def _nothing_yet(*_):
        return None

    monkeypatch.setattr(campaigns, "campaign_of", _nothing_yet)
    monkeypatch.setattr(accounts, "membership_refusal", _nothing_yet)

    reply = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json=_setup_body(world, new_candidate={"username": "peter"}),
    )

    assert reply.status_code == 400
    assert reply.json()["detail"] == (
        "That login is already on a campaign; a login belongs to one campaign."
    )


async def test_an_integrity_error_that_is_not_the_rule_is_not_dressed_up_as_it() -> None:
    from backend.main import app

    handler = app.exception_handlers[IntegrityError]
    other = IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: users.username"))

    with pytest.raises(IntegrityError):
        await handler(None, other)


async def test_regenerating_targets_picks_up_a_ward_added_later(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    session.add(Ward(constituency=world.constituency, name="Kahawa", registered_voters=17_428))
    await session.commit()

    response = await client.post(
        f"/api/campaigns/{world.campaign.id}/generate_targets/", headers=world.headers("manager")
    )

    assert response.status_code == 200
    assert response.json()["units"] == 3


async def test_a_candidate_may_not_regenerate_targets(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        f"/api/campaigns/{world.campaign.id}/generate_targets/", headers=world.headers("candidate")
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_no_campaign_role_deletes_a_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World, role: str
) -> None:
    response = await client.delete(
        f"/api/campaigns/{world.campaign.id}/", headers=world.headers(role)
    )

    assert response.status_code in (403, 404, 405)
    assert await session.get(Campaign, world.campaign.id) is not None
    assert await session.scalar(select(func.count()).select_from(Target)) == 2


@pytest.mark.parametrize("role", ["candidate", "manager", "mobilizer"])
async def test_everyone_on_a_campaign_is_told_whose_it_is_and_which_seat(
    client: httpx.AsyncClient, session: AsyncSession, world: World, role: str
) -> None:
    session.expunge_all()

    (campaign,) = (await client.get("/api/campaigns/", headers=world.headers(role))).json()

    assert campaign["candidate_username"] == "jane"
    assert campaign["candidate_name"] == "Amina Kariuki"
    assert "MP" in campaign["seat"]
    assert campaign["area_name"] == "Roysambu"
