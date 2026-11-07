"""2-step sign-in: turning it on, signing in with a code, recovery codes, and the gates."""

import asyncio
import contextlib

import pyotp
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartyRoleName, User, UserRole, UserTotp
from backend.services import two_step
from tests.conftest import POSTGRES
from tests.factories import (
    TEST_PASSWORD,
    auth,
    email_of,
    enrol_two_step,
    fresh_password,
    make_geography,
    make_officer,
    make_user,
    sign_in,
    site_settings,
    totp_code,
)


async def _password_only(client, username: str) -> dict:
    response = await client.post(
        "/api/auth/login/", json={"email": email_of(username), "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return auth(response.json()["token"])


async def test_a_login_turns_2_step_on_and_then_signs_in_only_with_a_code(client, session):
    await make_user(session, username="amina")
    headers = await _password_only(client, "amina")

    started = (await client.post("/api/auth/two-step/start/", headers=headers)).json()
    assert started["uri"].startswith("otpauth://totp/")
    code = pyotp.TOTP(started["secret"]).now()
    confirmed = await client.post(
        "/api/auth/two-step/confirm/", headers=headers, json={"code": code}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert len(confirmed.json()["codes"]) == 10

    body = {"email": email_of("amina"), "password": TEST_PASSWORD}
    asked = await client.post("/api/auth/login/", json=body)
    assert (asked.status_code, asked.json()["code_required"]) == (400, True)
    reused = await client.post("/api/auth/login/", json={**body, "code": code})
    assert reused.status_code == 400
    assert reused.json()["code_required"] is True


async def test_recovery_codes_work_once(client, session):
    await make_user(session, username="amina")
    headers = await _password_only(client, "amina")
    secret = (await client.post("/api/auth/two-step/start/", headers=headers)).json()["secret"]
    codes = (
        await client.post(
            "/api/auth/two-step/confirm/",
            headers=headers,
            json={"code": pyotp.TOTP(secret).now()},
        )
    ).json()["codes"]

    body = {"email": email_of("amina"), "password": TEST_PASSWORD, "code": codes[0]}
    first = await client.post("/api/auth/login/", json=body)
    again = await client.post("/api/auth/login/", json=body)

    assert first.status_code == 200, first.text
    assert again.status_code == 400
    left = (await client.get("/api/auth/two-step/", headers=auth(first.json()["token"]))).json()
    assert left["recovery_left"] == 9


async def test_the_superuser_cannot_reach_the_console_without_2_step(client, session):
    root = await make_user(session, username="root", role=UserRole.MANAGER)
    root.is_superuser = True
    await session.commit()
    headers = await _password_only(client, "root")

    refused = await client.get("/api/admin/campaigns/", headers=headers)
    me = (await client.get("/api/auth/me/", headers=headers)).json()

    assert (refused.status_code, refused.json()["code"]) == (403, "two_step_required")
    assert me["two_step_needed"] is True

    await enrol_two_step(session, root)
    passed = auth(await sign_in(client, "root"))
    assert (await client.get("/api/admin/campaigns/", headers=passed)).status_code == 200


async def test_turning_2_step_on_gives_a_new_token_and_ends_the_one_that_never_passed(
    client, session
):
    root = await make_user(session, username="root", role=UserRole.MANAGER)
    root.is_superuser = True
    await session.commit()
    stolen = await _password_only(client, "root")
    own = await _password_only(client, "root")
    assert stolen == own

    secret = (await client.post("/api/auth/two-step/start/", headers=own)).json()["secret"]
    confirmed = await client.post(
        "/api/auth/two-step/confirm/", headers=own, json={"code": pyotp.TOTP(secret).now()}
    )

    fresh = auth(confirmed.json()["token"])
    assert (await client.get("/api/admin/campaigns/", headers=stolen)).status_code == 401
    assert (await client.get("/api/admin/campaigns/", headers=fresh)).status_code == 200


@pytest.mark.party_only
async def test_a_staff_login_without_2_step_cannot_reach_party_routes_when_required(
    client, session
):
    session.add(site_settings(staff_two_step_required=True))
    _, _, ward, _ = await make_geography(session)
    officer = await make_officer(session, ward, PartyRoleName.MEMBERSHIP_OFFICER)
    headers = await _password_only(client, "ofisa")

    refused = await client.get("/api/party/members/", headers=headers)
    own = await client.get("/api/party/nominations/mine/", headers=headers)
    assert (refused.status_code, refused.json()["code"]) == (403, "two_step_required")
    assert (own.status_code, own.json()["code"]) == (403, "two_step_required")

    await enrol_two_step(session, officer)
    passed = auth(await sign_in(client, "ofisa"))
    assert (await client.get("/api/party/members/", headers=passed)).status_code == 200


async def test_a_reset_link_does_not_skip_2_step(client, session):
    from backend.models import LinkPurpose
    from backend.services import login_links

    user = await make_user(session, username="amina")
    await enrol_two_step(session, user)
    token = await login_links.issue(session, user, LinkPurpose.RESET)
    await session.commit()

    chosen = fresh_password()
    without = await client.post(f"/api/auth/links/{token}/", json={"password": chosen})
    with_code = await client.post(
        f"/api/auth/links/{token}/", json={"password": chosen, "code": totp_code()}
    )

    assert (without.status_code, without.json()["code_required"]) == (400, True)
    assert with_code.status_code == 200, with_code.text
    assert await session.scalar(select(func.count()).select_from(UserTotp)) == 1


@pytest.mark.skipif(not POSTGRES, reason="row locks need TEST_POSTGRES=1")
@pytest.mark.parametrize("kind", ["app", "recovery"])
async def test_one_code_sent_twice_at_once_passes_once(engine, session, kind, monkeypatch):
    user = await make_user(session, username="amina")
    secret = (await two_step.start(session, user))[0]
    codes = await two_step.confirm(session, user, pyotp.TOTP(secret).now())
    # Turning it on spent the current code; free it for the race.
    (await session.get(UserTotp, user.id)).last_step = 0
    await session.commit()
    code = pyotp.TOTP(secret).now() if kind == "app" else codes[0]

    # Each request waits, up to a second, for the other to read the row too: without the row
    # lock both read it unspent; with it the second waits for the first to commit.
    read, both = [], asyncio.Event()
    real = two_step._locked

    async def meet(own, who):
        row = await real(own, who)
        read.append(row)
        if len(read) == 2:
            both.set()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(both.wait(), 1)
        return row

    monkeypatch.setattr(two_step, "_locked", meet)

    async def attempt() -> bool:
        async with AsyncSession(engine, expire_on_commit=False) as own:
            passed = await two_step.check(own, await own.get(User, user.id), code)
            await own.commit()
            return passed

    assert sorted(await asyncio.gather(attempt(), attempt())) == [False, True]
