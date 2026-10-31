"""campaign-crm: each command parsed and run against the test database."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.cli import build_parser, run
from backend.models import User
from tests.conftest import World
from tests.factories import TEST_PASSWORD, sign_in


async def cli(session: AsyncSession, *argv: str) -> int:
    return await run(build_parser().parse_args(list(argv)), session)


async def test_createuser_makes_a_login_with_the_superuser_flag_only_when_asked(
    session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    assert (
        await cli(session, "createuser", "-u", "root", f"--password={TEST_PASSWORD}", "--superuser")
        == 0
    )
    assert await cli(session, "createuser", "-u", "plain", f"--password={TEST_PASSWORD}") == 0
    assert await cli(session, "createuser", "-u", "amina", f"--password={TEST_PASSWORD}") == 1

    flags = dict((await session.execute(select(User.username, User.is_superuser))).tuples().all())
    assert (flags["root"], flags["plain"]) == (True, False)
    printed = capsys.readouterr()
    assert "Created" in printed.out
    assert "The username amina is already taken." in printed.err


async def test_reset_password_hands_out_one_that_signs_in(
    client: httpx.AsyncClient, session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    assert await cli(session, "reset-password", "-u", "jane") == 0
    password = capsys.readouterr().out.splitlines()[0].rsplit(": ", 1)[1]
    assert await cli(session, "reset-password", "-u", "nobody") == 1

    assert await sign_in(client, "jane", password)
    assert "No user called nobody." in capsys.readouterr().err


async def test_reset_database_refuses_anything_but_postgres(
    session: AsyncSession, world: World, capsys: pytest.CaptureFixture
) -> None:
    assert await cli(session, "reset-database", "--yes", "anything") == 1

    assert await session.scalar(select(User.username).where(User.username == "jane")) == "jane"
    assert "Postgres only" in capsys.readouterr().err
