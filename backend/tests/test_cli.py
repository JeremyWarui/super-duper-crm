"""The command line jobs that repair what the API cannot reach.

`assign-manager` is the only way a campaign with no manager gets one, which is
the state every campaign is in until somebody sets one up.
"""

import argparse
import uuid

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.cli import (
    _add_member,
    _assign_manager,
    _campaign,
    _campaigns,
    _createuser,
    _remove_member,
    _reset_password,
    _set_active,
    _users,
    build_parser,
)
from backend.models import AuthToken, CampaignMember, User, UserRole
from tests.conftest import World
from tests.factories import auth, make_user, sign_in


async def _managers(session: AsyncSession, campaign_id) -> set:
    rows = await session.execute(
        select(CampaignMember.user_id).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.role == UserRole.MANAGER,
        )
    )
    return set(rows.scalars())


def _args(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**{"only": False, **kwargs})


async def test_listing_names_the_manager_of_each_campaign(
    session: AsyncSession, world: World, capsys
) -> None:
    assert await _campaigns(_args(), session) == 0

    printed = capsys.readouterr().out
    assert "Jane for Roysambu" in printed
    assert "candidate jane" in printed
    assert "managers amina" in printed
    assert "members 3" in printed


async def test_listing_says_when_a_campaign_has_no_manager(
    session: AsyncSession, world: World, capsys
) -> None:
    await session.execute(
        delete(CampaignMember).where(
            CampaignMember.campaign_id == world.campaign.id,
            CampaignMember.role == UserRole.MANAGER,
        )
    )
    await session.commit()

    await _campaigns(_args(), session)

    assert "-- none --" in capsys.readouterr().out


async def test_assigning_gives_the_manager_their_campaign_back(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The state every pre-existing campaign is in after the migration."""
    await session.execute(
        delete(CampaignMember).where(
            CampaignMember.campaign_id == world.campaign.id,
            CampaignMember.user_id == world.manager.id,
        )
    )
    await session.commit()
    token = await sign_in(client, "amina")
    assert (await client.get("/api/campaigns/", headers=auth(token))).json() == []

    assert await _assign_manager(_args(username="amina", campaign=world.campaign.id), session) == 0

    listed = (await client.get("/api/campaigns/", headers=auth(token))).json()
    assert [c["title"] for c in listed] == ["Jane for Roysambu"]


async def test_assigning_adds_a_manager_beside_the_one_already_there(
    session: AsyncSession, world: World
) -> None:
    """Memberships are additive, so this no longer evicts anybody."""
    rival = await make_user(session, username="rival", role=UserRole.MANAGER)

    code = await _assign_manager(_args(username="rival", campaign=world.campaign.id), session)

    assert code == 0
    assert await _managers(session, world.campaign.id) == {world.manager.id, rival.id}


async def test_only_takes_every_other_manager_off(session: AsyncSession, world: World) -> None:
    rival = await make_user(session, username="rival", role=UserRole.MANAGER)

    code = await _assign_manager(
        _args(username="rival", campaign=world.campaign.id, only=True), session
    )

    assert code == 0
    assert await _managers(session, world.campaign.id) == {rival.id}


async def test_assigning_twice_does_not_duplicate_the_membership(
    session: AsyncSession, world: World
) -> None:
    await _assign_manager(_args(username="amina", campaign=world.campaign.id), session)

    assert await _managers(session, world.campaign.id) == {world.manager.id}


async def test_assigning_refuses_somebody_who_is_not_a_manager(
    session: AsyncSession, world: World, capsys
) -> None:
    code = await _assign_manager(_args(username="jane", campaign=world.campaign.id), session)

    assert code == 1
    assert "not a campaign manager" in capsys.readouterr().err


async def test_assigning_refuses_an_unknown_user(
    session: AsyncSession, world: World, capsys
) -> None:
    code = await _assign_manager(_args(username="nobody", campaign=world.campaign.id), session)

    assert code == 1
    assert "No user called nobody" in capsys.readouterr().err


async def test_assigning_refuses_an_unknown_campaign(
    session: AsyncSession, world: World, capsys
) -> None:
    import uuid

    code = await _assign_manager(_args(username="amina", campaign=uuid.uuid4()), session)

    assert code == 1
    assert "No campaign with id" in capsys.readouterr().err


def test_the_parser_offers_both_new_commands() -> None:
    parser = build_parser()

    listed = parser.parse_args(["campaigns"])
    assert listed.handler is _campaigns

    assigned = parser.parse_args(
        ["assign-manager", "-u", "amina", "-c", "0f8f1b2c-0000-4000-8000-000000000001"]
    )
    assert assigned.handler is _assign_manager
    assert assigned.username == "amina"
    assert assigned.only is False


# ---------------------------------------------------------------- the console


def _person(username, **over):
    return _args(
        username=username,
        password="a-long-enough-password",
        role="manager",
        email="",
        first_name="",
        last_name="",
        phone="",
        **{"superuser": False, **over},
    )


async def test_createuser_mints_the_superuser_the_console_needs(
    session: AsyncSession, capsys
) -> None:
    """The only way a deployment gets its first admin, so it has to set the flag."""
    code = await _createuser(_person("root", superuser=True), session)

    assert code == 0
    root = await session.scalar(select(User).where(User.username == "root"))
    assert root.is_superuser is True
    assert "Created" in capsys.readouterr().out


async def test_createuser_leaves_the_flag_off_unless_it_is_asked_for(
    session: AsyncSession,
) -> None:
    await _createuser(_person("plain"), session)

    plain = await session.scalar(select(User).where(User.username == "plain"))
    assert plain.is_superuser is False


async def test_createuser_refuses_a_username_already_taken(
    session: AsyncSession, world: World, capsys
) -> None:
    code = await _createuser(_person("amina"), session)

    assert code == 1
    assert "already exists" in capsys.readouterr().err


async def test_users_lists_every_login_and_the_campaigns_it_reaches(
    session: AsyncSession, world: World, capsys
) -> None:
    assert await _users(_args(role=None, campaign=None), session) == 0

    printed = capsys.readouterr().out
    assert "amina" in printed
    assert "jane" in printed
    assert "Jane for Roysambu" in printed


async def test_users_can_be_narrowed_to_one_role(
    session: AsyncSession, world: World, capsys
) -> None:
    await _users(_args(role="mobilizer", campaign=None), session)

    printed = capsys.readouterr().out
    assert "juma" in printed
    assert "amina" not in printed


async def test_campaign_shows_one_campaign_and_its_team(
    session: AsyncSession, world: World, capsys
) -> None:
    assert await _campaign(_args(campaign=world.campaign.id), session) == 0

    printed = capsys.readouterr().out
    assert "Jane for Roysambu" in printed
    assert "amina" in printed


async def test_campaign_says_so_when_the_id_is_not_one(
    session: AsyncSession, world: World, capsys
) -> None:
    assert await _campaign(_args(campaign=uuid.uuid4()), session) == 1
    assert capsys.readouterr().err.strip() != ""


async def test_reset_password_hands_out_a_new_one_that_signs_in(
    client: httpx.AsyncClient, session: AsyncSession, world: World, capsys
) -> None:
    assert await _reset_password(_args(username="jane", password=None), session) == 0

    # "jane signs in with: <password>", then the warning line.
    password = capsys.readouterr().out.splitlines()[0].rsplit(": ", 1)[1]
    signed_in = await client.post(
        "/api/auth/login/", json={"username": "jane", "password": password}
    )
    assert signed_in.status_code == 200, signed_in.text


async def test_reset_password_refuses_a_login_that_is_not_there(
    session: AsyncSession, capsys
) -> None:
    assert await _reset_password(_args(username="nobody", password=None), session) == 1
    assert "nobody" in capsys.readouterr().err


async def test_deactivate_stops_a_live_session_and_activate_lets_it_back(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    token = await sign_in(client, "amina")
    assert (await client.get("/api/campaigns/", headers=auth(token))).status_code == 200

    assert await _set_active(_args(username="amina", active=False), session) == 0

    assert (await client.get("/api/campaigns/", headers=auth(token))).status_code == 401
    assert not (await session.execute(select(AuthToken).where(AuthToken.key == token))).first()

    assert await _set_active(_args(username="amina", active=True), session) == 0
    again = await sign_in(client, "amina")
    assert (await client.get("/api/campaigns/", headers=auth(again))).status_code == 200


async def test_add_member_puts_somebody_back_on_a_campaign(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """The recovery path for anybody the console or the CLI took off."""
    assert await _remove_member(_args(username="juma", campaign=world.campaign.id), session) == 0
    token = await sign_in(client, "juma")
    assert (await client.get("/api/campaigns/", headers=auth(token))).json() == []

    assert await _add_member(_args(username="juma", campaign=world.campaign.id), session) == 0

    back = await sign_in(client, "juma")
    assert [c["id"] for c in (await client.get("/api/campaigns/", headers=auth(back))).json()] == [
        str(world.campaign.id)
    ]


async def test_add_member_gives_them_the_place_their_login_carries(
    session: AsyncSession, world: World, capsys
) -> None:
    await _remove_member(_args(username="juma", campaign=world.campaign.id), session)

    await _add_member(_args(username="juma", campaign=world.campaign.id), session)

    assert "mobilizer" in capsys.readouterr().out
    role = await session.scalar(
        select(CampaignMember.role).where(
            CampaignMember.campaign_id == world.campaign.id,
            CampaignMember.user_id == world.mobilizer_user.id,
        )
    )
    assert role is UserRole.MOBILIZER


async def test_add_member_refuses_a_login_that_is_not_there(
    session: AsyncSession, world: World, capsys
) -> None:
    assert await _add_member(_args(username="nobody", campaign=world.campaign.id), session) == 1
    assert "nobody" in capsys.readouterr().err


async def test_remove_member_refuses_to_take_the_candidate_off(
    session: AsyncSession, world: World, capsys
) -> None:
    assert await _remove_member(_args(username="jane", campaign=world.campaign.id), session) == 1
    assert "candidate" in capsys.readouterr().err


def test_the_parser_wires_every_console_command() -> None:
    parser = build_parser()
    campaign_id = "0f8f1b2c-0000-4000-8000-000000000001"

    assert parser.parse_args(["users"]).handler is _users
    assert parser.parse_args(["campaign", "-c", campaign_id]).handler is _campaign
    assert parser.parse_args(["reset-password", "-u", "jane"]).handler is _reset_password
    assert parser.parse_args(["add-member", "-u", "jane", "-c", campaign_id]).handler is _add_member
    assert (
        parser.parse_args(["remove-member", "-u", "jane", "-c", campaign_id]).handler
        is _remove_member
    )
    off = parser.parse_args(["deactivate", "-u", "jane"])
    assert off.handler is _set_active and off.active is False
    on = parser.parse_args(["activate", "-u", "jane"])
    assert on.handler is _set_active and on.active is True
    assert parser.parse_args(["createuser", "-u", "root", "-r", "manager", "--superuser"]).superuser


async def test_deactivate_refuses_the_last_superuser(
    session: AsyncSession, world: World, capsys
) -> None:
    """Nothing could reach the console afterwards, and no route can undo it."""
    await _createuser(_person("root", superuser=True), session)

    assert await _set_active(_args(username="root", active=False), session) == 1

    assert "only superuser" in capsys.readouterr().err
    root = await session.scalar(select(User).where(User.username == "root"))
    assert root.is_active is True


async def test_deactivate_shuts_off_a_superuser_when_another_is_left(
    session: AsyncSession, world: World
) -> None:
    """A compromised admin account has to be stoppable."""
    await _createuser(_person("root", superuser=True), session)
    await _createuser(_person("spare_root", superuser=True), session)

    assert await _set_active(_args(username="spare_root", active=False), session) == 0

    spare = await session.scalar(select(User).where(User.username == "spare_root"))
    assert spare.is_active is False
