"""Campaign reads, and the one call that stands a new campaign up."""

import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.scope import add_member
from backend.config import get_settings
from backend.models import Campaign, CampaignMember, Target, User, UserRole
from tests.conftest import World
from tests.factories import auth, make_user, sign_in


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


async def test_a_candidate_sees_their_own_campaign(client: httpx.AsyncClient, world: World) -> None:
    body = (await client.get("/api/campaigns/", headers=world.headers("candidate"))).json()
    assert [c["id"] for c in body] == [str(world.campaign.id)]


async def test_a_candidate_does_not_see_somebody_else_s_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    rival = await make_user(session, username="rival", role=UserRole.CANDIDATE)
    theirs = Campaign(
        title="Rival for Roysambu",
        office_level=world.campaign.office_level,
        constituency_id=world.constituency.id,
    )
    session.add(theirs)
    await session.flush()
    await add_member(session, theirs.id, rival.id)
    await session.commit()

    body = (await client.get("/api/campaigns/", headers=world.headers("candidate"))).json()

    assert [c["title"] for c in body] == ["Jane for Roysambu"]


async def test_a_mobilizer_sees_the_campaign_they_organize_for(
    client: httpx.AsyncClient, world: World
) -> None:
    body = (await client.get("/api/campaigns/", headers=world.headers("mobilizer"))).json()
    assert [c["id"] for c in body] == [str(world.campaign.id)]


async def test_a_mobilizer_with_no_profile_sees_no_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await make_user(session, username="stray", role=UserRole.MOBILIZER)
    token = await sign_in(client, "stray")

    assert (await client.get("/api/campaigns/", headers=auth(token))).json() == []


async def test_fetching_a_campaign_that_is_not_yours_is_404(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    rival = await make_user(session, username="rival", role=UserRole.CANDIDATE)
    other = Campaign(
        title="Rival for Roysambu",
        office_level=world.campaign.office_level,
        constituency_id=world.constituency.id,
    )
    session.add(other)
    await session.flush()
    await add_member(session, other.id, rival.id)
    await session.commit()

    response = await client.get(f"/api/campaigns/{other.id}/", headers=world.headers("candidate"))

    assert response.status_code == 404


# ------------------------------------------------------------------- setup


async def test_setup_creates_the_campaign_and_all_of_its_targets(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json={
            "title": "Amina for Roysambu",
            "office_level": "constituency",
            "election_date": "2027-08-10",
            "constituency": str(world.constituency.id),
            "candidate": str(world.candidate.id),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Amina for Roysambu"
    assert body["election_date"] == "2027-08-10"
    assert body["setup"]["grain"] == "ward"
    assert body["setup"]["units"] == 2
    assert body["setup"]["total_registered"] == 66_600
    assert body["setup"]["note"] is None

    created = await session.get(Campaign, uuid.UUID(body["id"]))
    assert created is not None
    assert (
        await session.scalar(
            select(func.count()).select_from(Target).where(Target.campaign_id == created.id)
        )
        == 2
    )


async def test_the_setup_summary_totals_the_win_number(
    client: httpx.AsyncClient, world: World
) -> None:
    """Zimmerman 30,701 and Githurai 35,899 at 60% turnout: 9,211 + 10,770."""
    body = (
        await client.post(
            "/api/campaigns/setup/",
            headers=world.headers("manager"),
            json={
                "title": "Amina for Roysambu",
                "office_level": "constituency",
                "constituency": str(world.constituency.id),
                "candidate": str(world.candidate.id),
            },
        )
    ).json()

    assert body["setup"]["win_number"] == 19_981


async def test_a_candidate_may_set_their_own_campaign_up(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("candidate"),
        json={
            "title": "Jane for Governor",
            "office_level": "county",
            "county": str(world.county.id),
        },
    )

    assert response.status_code == 201
    assert response.json()["candidate"] == str(world.candidate.id)


async def test_a_mobilizer_may_not_set_a_campaign_up(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("mobilizer"),
        json={
            "title": "Juma for Roysambu",
            "office_level": "constituency",
            "constituency": str(world.constituency.id),
        },
    )

    assert response.status_code == 403


async def test_setup_needs_the_area_that_matches_the_office(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json={
            "title": "Amina for Roysambu",
            "office_level": "constituency",
            "county": str(world.county.id),
            "candidate": str(world.candidate.id),
        },
    )

    assert response.status_code == 400
    assert "constituency" in response.json()["detail"]


async def test_an_unknown_office_level_is_one_readable_sentence(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json={"title": "Amina", "office_level": "president"},
    )

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)


async def test_an_mca_campaign_with_no_centres_says_so_in_the_summary(
    client: httpx.AsyncClient, world: World
) -> None:
    body = (
        await client.post(
            "/api/campaigns/setup/",
            headers=world.headers("manager"),
            json={
                "title": "Amina for Githurai",
                "office_level": "ward",
                "ward": str(world.other_ward.id),
                "candidate": str(world.candidate.id),
            },
        )
    ).json()

    assert body["setup"]["grain"] == "centre"
    assert body["setup"]["units"] == 0
    assert "Githurai" in body["setup"]["note"]


# -------------------------------------------------------- regenerate, delete


async def test_regenerating_targets_picks_up_a_ward_added_later(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from backend.models import Ward

    session.add(Ward(constituency=world.constituency, name="Kahawa", registered_voters=17_428))
    await session.commit()

    response = await client.post(
        f"/api/campaigns/{world.campaign.id}/generate_targets/",
        headers=world.headers("manager"),
    )

    assert response.status_code == 200
    assert response.json()["units"] == 3


async def test_a_candidate_may_not_regenerate_targets(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        f"/api/campaigns/{world.campaign.id}/generate_targets/",
        headers=world.headers("candidate"),
    )
    assert response.status_code == 403


async def test_deleting_a_campaign_takes_its_targets_with_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.delete(
        f"/api/campaigns/{world.campaign.id}/", headers=world.headers("manager")
    )

    assert response.status_code == 204
    assert await session.scalar(select(func.count()).select_from(Target)) == 0


# ------------------------------------------------- whose campaign it is


def _setup_body(world: World, **overrides) -> dict:
    body = {
        "title": "Peter for Kasarani",
        "office_level": "constituency",
        "constituency": str(world.constituency.id),
    }
    body.update(overrides)
    return body


async def test_a_manager_must_say_who_the_campaign_is_for(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/", headers=world.headers("manager"), json=_setup_body(world)
    )

    assert response.status_code == 400
    assert "who this campaign is for" in response.json()["detail"]


async def test_a_manager_sets_a_campaign_up_for_an_existing_aspirant(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json=_setup_body(world, candidate=str(world.candidate.id)),
    )

    assert response.status_code == 201
    assert response.json()["candidate"] == str(world.candidate.id)
    assert response.json()["candidate_login"] is None


async def test_the_aspirant_sees_the_campaign_a_manager_made_for_them(
    client: httpx.AsyncClient, world: World
) -> None:
    await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json=_setup_body(world, candidate=str(world.candidate.id)),
    )

    mine = (await client.get("/api/campaigns/", headers=world.headers("candidate"))).json()

    assert "Peter for Kasarani" in {c["title"] for c in mine}


async def test_a_manager_creates_the_aspirant_and_gets_their_password_once(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json=_setup_body(
            world,
            new_candidate={"username": "peter", "first_name": "Peter", "last_name": "Kimani"},
        ),
    )

    assert response.status_code == 201
    login = response.json()["candidate_login"]
    assert login["username"] == "peter"
    assert len(login["password"]) >= 12
    assert response.json()["candidate"] == login["id"]

    created = (await session.execute(select(User).where(User.username == "peter"))).scalar_one()
    assert created.role is UserRole.CANDIDATE


async def test_the_default_password_reaches_the_aspirant_created_at_setup(
    client: httpx.AsyncClient, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEFAULT_USER_PASSWORD", "campaign1234")
    get_settings.cache_clear()
    try:
        response = await client.post(
            "/api/campaigns/setup/",
            headers=world.headers("manager"),
            json=_setup_body(world, new_candidate={"username": "peter"}),
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 201
    assert response.json()["candidate_login"]["password"] == "campaign1234"


async def test_that_new_aspirant_can_sign_in_and_see_their_campaign(
    client: httpx.AsyncClient, world: World
) -> None:
    created = (
        await client.post(
            "/api/campaigns/setup/",
            headers=world.headers("manager"),
            json=_setup_body(world, new_candidate={"username": "peter", "first_name": "Peter"}),
        )
    ).json()

    token = await sign_in(client, "peter", created["candidate_login"]["password"])
    mine = (await client.get("/api/campaigns/", headers=auth(token))).json()

    assert [c["title"] for c in mine] == ["Peter for Kasarani"]


async def test_a_manager_cannot_both_name_and_create_an_aspirant(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json=_setup_body(
            world,
            candidate=str(world.candidate.id),
            new_candidate={"username": "peter"},
        ),
    )
    assert response.status_code == 400


async def test_a_campaign_cannot_be_hung_on_somebody_who_is_not_an_aspirant(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json=_setup_body(world, candidate=str(world.mobilizer_user.id)),
    )

    assert response.status_code == 400
    assert "not an aspirant" in response.json()["detail"]


async def test_an_unknown_aspirant_is_refused(client: httpx.AsyncClient, world: World) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json=_setup_body(world, candidate="00000000-0000-0000-0000-000000000009"),
    )
    assert response.status_code == 400


async def test_a_username_already_taken_is_refused_before_the_campaign_is_made(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json=_setup_body(world, new_candidate={"username": "jane"}),
    )

    assert response.status_code == 400
    assert (
        await session.scalar(
            select(func.count()).select_from(Campaign).where(Campaign.title == "Peter for Kasarani")
        )
        == 0
    )


async def test_a_candidate_still_gets_their_own_campaign(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/", headers=world.headers("candidate"), json=_setup_body(world)
    )

    assert response.status_code == 201
    assert response.json()["candidate"] == str(world.candidate.id)


async def test_a_candidate_cannot_set_a_campaign_up_for_somebody_else(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    rival = await make_user(session, username="rival", role=UserRole.CANDIDATE)

    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("candidate"),
        json=_setup_body(world, candidate=str(rival.id)),
    )

    assert response.status_code == 403


async def test_a_candidate_cannot_create_another_candidate(
    client: httpx.AsyncClient, world: World
) -> None:
    response = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("candidate"),
        json=_setup_body(world, new_candidate={"username": "peter"}),
    )
    assert response.status_code == 400


async def test_a_fresh_manager_owns_nothing_so_the_browser_sends_them_to_setup(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """An empty list is what makes the sign-up flow ask who the campaign is for."""
    await make_user(session, username="newmanager", role=UserRole.MANAGER)
    token = await sign_in(client, "newmanager")

    body = (await client.get("/api/campaigns/", headers=auth(token))).json()

    assert body == []


async def test_a_manager_does_not_see_another_manager_s_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await make_user(session, username="rival", role=UserRole.MANAGER)
    token = await sign_in(client, "rival")

    body = (await client.get("/api/campaigns/", headers=auth(token))).json()

    assert [c["id"] for c in body] == []
    assert (
        await client.get(f"/api/campaigns/{world.campaign.id}/", headers=auth(token))
    ).status_code == 404


async def _members(session: AsyncSession, campaign_id: uuid.UUID) -> dict[str, str]:
    """username -> role on that campaign."""
    rows = await session.execute(
        select(User.username, CampaignMember.role)
        .join(CampaignMember, CampaignMember.user_id == User.id)
        .where(CampaignMember.campaign_id == campaign_id)
    )
    return {username: role.value for username, role in rows}


async def test_setting_a_campaign_up_puts_its_candidate_and_its_manager_on_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    reply = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json={
            "title": "Amina for Githurai",
            "office_level": "ward",
            "ward": str(world.other_ward.id),
            "new_candidate": {"username": "peter", "first_name": "Peter"},
        },
    )

    assert reply.status_code == 201, reply.text
    members = await _members(session, uuid.UUID(reply.json()["id"]))
    assert members == {"peter": "candidate", "amina": "manager"}


async def test_a_manager_sees_the_campaign_they_just_set_up_and_no_other(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await make_user(session, username="newmanager", role=UserRole.MANAGER)
    token = await sign_in(client, "newmanager")
    reply = await client.post(
        "/api/campaigns/setup/",
        headers=auth(token),
        json={
            "title": "Peter for Githurai",
            "office_level": "ward",
            "ward": str(world.other_ward.id),
            "new_candidate": {"username": "peter", "first_name": "Peter"},
        },
    )
    assert reply.status_code == 201, reply.text

    body = (await client.get("/api/campaigns/", headers=auth(token))).json()

    assert [c["title"] for c in body] == ["Peter for Githurai"]


async def test_a_campaign_a_candidate_stood_up_alone_has_only_them_on_it(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    reply = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("candidate"),
        json={
            "title": "Jane for Githurai",
            "office_level": "ward",
            "ward": str(world.other_ward.id),
        },
    )

    assert reply.status_code == 201, reply.text
    assert await _members(session, uuid.UUID(reply.json()["id"])) == {"jane": "candidate"}


async def test_the_aspirant_still_sees_a_campaign_their_manager_set_up(
    client: httpx.AsyncClient, world: World
) -> None:
    """Scoping the manager must not take the campaign away from whose it is."""
    body = (await client.get("/api/campaigns/", headers=world.headers("candidate"))).json()

    assert [c["id"] for c in body] == [str(world.campaign.id)]


async def test_adding_somebody_already_on_the_campaign_neither_duplicates_nor_moves_them(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await add_member(session, world.campaign.id, world.candidate.id)
    await session.commit()

    rows = await session.execute(
        select(func.count())
        .select_from(CampaignMember)
        .where(
            CampaignMember.campaign_id == world.campaign.id,
            CampaignMember.user_id == world.candidate.id,
        )
    )

    assert rows.scalar_one() == 1
    body = (await client.get("/api/campaigns/", headers=world.headers("candidate"))).json()
    assert [c["id"] for c in body] == [str(world.campaign.id)]
    assert await _members(session, world.campaign.id) == {
        "jane": "candidate",
        "amina": "manager",
        "juma": "mobilizer",
    }


async def test_a_manager_may_run_more_than_one_campaign(
    client: httpx.AsyncClient, world: World
) -> None:
    """A single column could not hold this; a membership row can."""
    made = await client.post(
        "/api/campaigns/setup/",
        headers=world.headers("manager"),
        json={
            "title": "Amina for Githurai",
            "office_level": "ward",
            "ward": str(world.other_ward.id),
            "new_candidate": {"username": "peter"},
        },
    )
    assert made.status_code == 201, made.text

    listed = (await client.get("/api/campaigns/", headers=world.headers("manager"))).json()

    assert sorted(c["title"] for c in listed) == ["Amina for Githurai", "Jane for Roysambu"]


async def test_deleting_a_manager_leaves_their_campaign_standing(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Losing a member must not take the campaign with them."""
    manager = await session.get(User, world.manager.id)
    assert manager is not None
    await session.delete(manager)
    await session.commit()

    row = (
        await session.execute(select(Campaign.id).where(Campaign.id == world.campaign.id))
    ).one_or_none()
    assert row is not None, "the campaign was deleted with its manager"
    assert await _members(session, world.campaign.id) == {"jane": "candidate", "juma": "mobilizer"}
