"""campaign-crm: each command parsed and run against the test database."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.cli import build_parser, run
from backend.models import AuthToken, Campaign, OfficeLevel, User
from tests.conftest import World
from tests.factories import TEST_PASSWORD, auth, make_rival_campaign, members_of, sign_in

MISSING = str(uuid.uuid4())


async def cli(session: AsyncSession, *argv: str) -> int:
    return await run(build_parser().parse_args(list(argv)), session)


async def test_createuser_makes_a_login_with_the_superuser_flag_only_when_asked(
    session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    assert await cli(session, "createuser", "-u", "root", "-p", TEST_PASSWORD, "--superuser") == 0
    assert await cli(session, "createuser", "-u", "plain", "-p", TEST_PASSWORD) == 0
    assert await cli(session, "createuser", "-u", "amina", "-p", TEST_PASSWORD) == 1

    flags = dict((await session.execute(select(User.username, User.is_superuser))).tuples().all())
    assert (flags["root"], flags["plain"]) == (True, False)
    printed = capsys.readouterr()
    assert "Created" in printed.out
    assert "The username amina is already taken." in printed.err


async def test_campaign_lists_every_campaign_or_shows_one_in_full(
    session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    assert await cli(session, "campaign") == 0
    listed = capsys.readouterr().out
    assert await cli(session, "campaign", "-c", str(world.campaign.id)) == 0
    one = capsys.readouterr().out
    assert await cli(session, "campaign", "-c", MISSING) == 1
    missing_err = capsys.readouterr().err
    bare = Campaign(
        title="Githurai MCA", office_level=OfficeLevel.WARD, ward_id=world.other_ward.id
    )
    session.add(bare)
    await session.commit()
    assert await cli(session, "campaign", "-c", str(bare.id)) == 0

    assert "Jane for Roysambu  candidate jane  members 3" in listed
    assert "candidate  -- none --" in capsys.readouterr().out
    assert "manager    amina" in one
    assert "targets    2" in one
    assert "No such campaign." in missing_err


async def test_users_lists_each_login_with_its_campaign_and_narrows_by_role(
    session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    assert await cli(session, "users") == 0
    everyone = capsys.readouterr().out
    assert await cli(session, "users", "-r", "mobilizer") == 0
    mobilizers = capsys.readouterr().out

    assert "amina" in everyone and "Jane for Roysambu" in everyone
    assert "juma" in mobilizers and "amina" not in mobilizers


async def test_reset_password_hands_out_one_that_signs_in(
    client: httpx.AsyncClient, session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    assert await cli(session, "reset-password", "-u", "jane") == 0
    password = capsys.readouterr().out.splitlines()[0].rsplit(": ", 1)[1]
    assert await cli(session, "reset-password", "-u", "nobody") == 1

    assert await sign_in(client, "jane", password)
    assert "No user called nobody." in capsys.readouterr().err


async def test_deactivate_stops_a_session_and_activate_lets_it_back(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    token = await sign_in(client, "amina")

    assert await cli(session, "deactivate", "-u", "amina") == 0
    assert (await client.get("/api/campaigns/", headers=auth(token))).status_code == 401
    assert await session.scalar(select(AuthToken).where(AuthToken.key == token)) is None

    assert await cli(session, "activate", "-u", "amina") == 0
    assert await sign_in(client, "amina")


async def test_deactivate_keeps_the_last_superuser_on(
    session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    await cli(session, "createuser", "-u", "root", "-p", TEST_PASSWORD, "--superuser")
    await cli(session, "createuser", "-u", "spare", "-p", TEST_PASSWORD, "--superuser")

    assert await cli(session, "deactivate", "-u", "spare") == 0
    assert await cli(session, "deactivate", "-u", "root") == 1
    assert "only superuser" in capsys.readouterr().err


async def test_remove_member_and_add_member_move_a_login_off_and_back(
    client: httpx.AsyncClient, session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    campaign = str(world.campaign.id)

    assert await cli(session, "remove-member", "-u", "juma", "-c", campaign) == 0
    assert (
        await client.get("/api/campaigns/", headers=auth(await sign_in(client, "juma")))
    ).json() == []
    assert await cli(session, "add-member", "-u", "juma", "-c", campaign) == 0

    assert "is on that campaign as its mobilizer" in capsys.readouterr().out
    assert (await members_of(session, world.campaign.id))["juma"] == "mobilizer"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["add-member", "-u", "nobody"], "No user called nobody."),
        (["add-member", "-u", "jane", "-c", "{rival}"], "jane is already on Jane for Roysambu"),
        (["remove-member", "-u", "jane"], "delete the campaign instead"),
        (["rename-campaign", "-t", "  "], "A campaign needs a name."),
    ],
)
async def test_a_membership_command_that_cannot_happen_says_why(
    session: AsyncSession,
    world: World,
    capsys: pytest.CaptureFixture,
    argv: list[str],
    message: str,
) -> None:
    rival = await make_rival_campaign(session, world.other_ward)
    campaign = str(rival.id) if "{rival}" in argv else str(world.campaign.id)
    argv = [campaign if a == "{rival}" else a for a in argv]
    if "-c" not in argv:
        argv += ["-c", campaign]

    assert await cli(session, *argv) == 1
    assert message in capsys.readouterr().err


async def test_rename_campaign_changes_the_name(session: AsyncSession, world: World) -> None:
    assert (
        await cli(session, "rename-campaign", "-c", str(world.campaign.id), "-t", " Jane 2027 ")
        == 0
    )

    assert await session.scalar(select(Campaign.title)) == "Jane 2027"


async def test_delete_campaign_says_what_and_who_would_go_then_deletes_with_yes(
    session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    campaign = str(world.campaign.id)

    assert await cli(session, "delete-campaign", "-c", campaign) == 1
    said = capsys.readouterr().err
    assert await session.get(Campaign, world.campaign.id) is not None
    assert await cli(session, "delete-campaign", "-c", campaign, "--yes") == 0
    done = capsys.readouterr().out
    assert await cli(session, "delete-campaign", "-c", MISSING, "--yes") == 1

    assert "Jane for Roysambu with 2 targets, 1 mobilizers" in said
    assert "3 logins (amina, jane, juma)" in said
    assert "--yes" in said
    assert "Deleted Jane for Roysambu and 3 logins: amina, jane, juma." in done
    assert await session.get(Campaign, world.campaign.id) is None
    assert list(await session.scalars(select(User.username))) == []
    assert "No such campaign." in capsys.readouterr().err
