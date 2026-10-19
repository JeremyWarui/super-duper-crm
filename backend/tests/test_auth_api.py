"""Signing up, signing in, signing out, and what an unknown or stale token gets."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import User, UserRole
from tests.factories import TEST_PASSWORD, auth, fresh_password, make_user, sign_in

SIGNUP_PASSWORD = fresh_password()


async def test_signing_in_returns_a_token_and_the_caller(
    client: httpx.AsyncClient, session
) -> None:
    await make_user(session, username="amina", role=UserRole.MANAGER)

    response = await client.post(
        "/api/auth/login/", json={"username": "amina", "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["token"]) == 40
    assert body["user"]["username"] == "amina"
    assert body["user"]["full_name"] == "Amina Kariuki"
    assert body["user"]["role"] == "manager"


async def test_a_wrong_password_is_rejected_in_the_shape_the_form_reads(
    client: httpx.AsyncClient, session
) -> None:
    await make_user(session, username="amina")
    response = await client.post(
        "/api/auth/login/", json={"username": "amina", "password": fresh_password()}
    )
    assert response.status_code == 400
    body = response.json()
    assert body["non_field_errors"][0] == body["detail"]
    assert "credentials" in body["detail"]


async def test_an_unknown_username_gets_the_same_message_as_a_wrong_password(
    client: httpx.AsyncClient, session
) -> None:
    await make_user(session, username="amina")
    guess = fresh_password()
    unknown = await client.post("/api/auth/login/", json={"username": "ghost", "password": guess})
    wrong = await client.post("/api/auth/login/", json={"username": "amina", "password": guess})
    assert unknown.status_code == wrong.status_code == 400
    assert unknown.json() == wrong.json()


async def test_a_deactivated_user_cannot_sign_in(client: httpx.AsyncClient, session) -> None:
    await make_user(session, username="amina", is_active=False)
    response = await client.post(
        "/api/auth/login/", json={"username": "amina", "password": TEST_PASSWORD}
    )
    assert response.status_code == 400


async def test_a_token_stops_working_once_signed_out(client: httpx.AsyncClient, session) -> None:
    await make_user(session, username="amina")
    token = await sign_in(client, "amina")
    await client.post("/api/auth/logout/", headers=auth(token))

    response = await client.post("/api/auth/logout/", headers=auth(token))

    assert response.status_code == 401


async def test_no_token_is_401(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/auth/logout/")
    assert response.status_code == 401
    assert "not provided" in response.json()["detail"]


def _signup(**overrides) -> dict:
    body = {
        "username": "newaspirant2",
        "password": SIGNUP_PASSWORD,
        "role": "candidate",
        "first_name": "Jane",
        "last_name": "Wanjiru",
    }
    body.update(overrides)
    return body


async def test_signing_up_creates_the_account_and_signs_it_in(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    response = await client.post("/api/auth/register/", json=_signup())

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["username"] == "newaspirant2"
    assert body["user"]["role"] == "candidate"
    assert body["token"]

    created = (
        await session.execute(select(User).where(User.username == "newaspirant2"))
    ).scalar_one()
    assert created.role is UserRole.CANDIDATE
    assert not created.is_superuser


async def test_a_mobilizer_cannot_sign_up(client: httpx.AsyncClient) -> None:
    """They need a campaign and a ward, so they are invited from inside one."""
    assert (
        await client.post("/api/auth/register/", json=_signup(role="mobilizer"))
    ).status_code == 400


async def test_signing_up_cannot_make_a_superuser(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    reply = await client.post("/api/auth/register/", json=_signup(is_superuser=True))

    assert reply.status_code == 400
    assert await session.scalar(select(User).where(User.username == "newaspirant2")) is None
