"""Password reset and invite links: same answer for any address, one use, expiry, rate limits."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import EmailLog, LoginInvite
from tests.conftest import World
from tests.factories import claim_link, email_of, fresh_password, link_token, sign_in

RESET = "/api/auth/password-reset/"


async def _emails_to(session: AsyncSession, address: str) -> int:
    return len((await session.scalars(select(EmailLog).where(EmailLog.to == address))).all())


async def test_the_reset_reply_is_the_same_for_a_known_and_an_unknown_email(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    known = await client.post(RESET, json={"email": email_of("jane")})
    unknown = await client.post(RESET, json={"email": "nobody@example.test"})

    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())
    assert await _emails_to(session, email_of("jane")) == 1
    assert await _emails_to(session, "nobody@example.test") == 0


async def test_a_link_works_once_and_not_after_it_expires(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await client.post(RESET, json={"email": email_of("jane")})
    token = await link_token(session, email_of("jane"))
    chosen = fresh_password()

    first = await client.post(f"/api/auth/links/{token}/", json={"password": chosen})
    again = await client.post(f"/api/auth/links/{token}/", json={"password": fresh_password()})
    await client.post(RESET, json={"email": email_of("jane")})
    await session.execute(
        update(LoginInvite).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await session.commit()
    stale = await link_token(session, email_of("jane"))
    expired = await client.post(f"/api/auth/links/{stale}/", json={"password": fresh_password()})

    assert first.status_code == 200, first.text
    assert again.status_code == 400
    assert expired.status_code == 400
    assert await sign_in(client, "jane", chosen)


async def test_resets_are_rate_limited_per_address_and_per_device(
    client: httpx.AsyncClient, world: World
) -> None:
    same_address = [
        (await client.post(RESET, json={"email": email_of("jane")})).status_code for _ in range(4)
    ]
    other_addresses = [
        (await client.post(RESET, json={"email": f"x{n}@example.test"})).status_code
        for n in range(2)
    ]

    assert same_address == [200, 200, 200, 429]
    # The device has made 5 requests by now; the 6th is refused whatever the address.
    assert other_addresses == [200, 429]


async def test_an_invite_sets_the_password_and_the_login_then_signs_in(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    made = await client.post(
        f"/api/campaigns/{world.campaign.id}/team/",
        headers=world.headers("candidate"),
        json={"username": "otieno", "email": "otieno@example.test", "role": "comms"},
    )
    chosen = fresh_password()

    token = await link_token(session, "otieno@example.test")
    seen = await client.get(f"/api/auth/links/{token}/")
    await claim_link(client, session, "otieno@example.test", chosen)

    assert made.json()["invite"] == "email"
    assert seen.json() == {
        "purpose": "invite",
        "username": "otieno",
        "email": "otieno@example.test",
    }
    assert await sign_in(client, "otieno@example.test", chosen)


async def test_the_email_log_never_holds_a_link_token(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await client.post(RESET, json={"email": email_of("jane")})
    token = await link_token(session, email_of("jane"))

    logged = await session.scalar(select(EmailLog.body).where(EmailLog.to == email_of("jane")))

    assert token not in logged
    assert "/reset/[removed]" in logged


async def test_a_turned_off_login_cannot_use_its_link(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    await client.post(RESET, json={"email": email_of("amina")})
    token = await link_token(session, email_of("amina"))
    world.manager.is_active = False
    await session.commit()

    response = await client.post(f"/api/auth/links/{token}/", json={"password": fresh_password()})

    assert response.status_code == 400


async def test_a_link_spent_after_it_was_read_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World, monkeypatch
) -> None:
    from backend.services import login_links
    from backend.services.errors import Refused

    await client.post(RESET, json={"email": email_of("jane")})
    token = await link_token(session, email_of("jane"))
    read = await login_links._live(session, token)
    await session.execute(update(LoginInvite).values(used_at=datetime.now(UTC)))

    async def stale(_session, _token):
        return read

    monkeypatch.setattr(login_links, "_live", stale)
    try:
        await login_links.claim(session, token, fresh_password())
    except Refused:
        refused = True
    else:
        refused = False

    assert refused


@pytest.mark.party_only
async def test_a_member_not_yet_approved_gets_no_reset_and_cannot_use_a_link(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    from backend.models import LinkPurpose, User
    from backend.services import login_links
    from backend.services.email import PracticeEmailProvider
    from tests.test_account_api import APPLICANT, _joined

    await _joined(client, session, world)
    asked = await client.post(RESET, json={"email": APPLICANT})
    login = await session.scalar(select(User).where(User.email == APPLICANT))
    token = await login_links.issue(session, login, LinkPurpose.RESET)
    await session.commit()

    claimed = await client.post(f"/api/auth/links/{token}/", json={"password": fresh_password()})

    assert asked.status_code == 200
    assert not [to for to, _, _ in PracticeEmailProvider.outbox if to == APPLICANT]
    assert claimed.status_code == 400
