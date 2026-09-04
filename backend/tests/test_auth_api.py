"""Signing in, signing out, and what an unknown or stale token gets."""

import httpx
from sqlalchemy import select

from backend.models import AuthToken, UserRole
from tests.factories import auth, make_user, sign_in


async def test_signing_in_returns_a_token_and_the_caller(
    client: httpx.AsyncClient, session
) -> None:
    await make_user(session, username="amina", role=UserRole.MANAGER)

    response = await client.post(
        "/api/auth/login/", json={"username": "amina", "password": "correct-horse-battery"}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["token"]) == 40
    assert body["user"]["username"] == "amina"
    assert body["user"]["full_name"] == "Amina Kariuki"
    assert body["user"]["role"] == "manager"


async def test_the_response_carries_no_password_hash(client: httpx.AsyncClient, session) -> None:
    await make_user(session, username="amina")
    response = await client.post(
        "/api/auth/login/", json={"username": "amina", "password": "correct-horse-battery"}
    )
    assert "password_hash" not in response.text


async def test_signing_in_twice_reuses_the_same_token(client: httpx.AsyncClient, session) -> None:
    """A second device signs in without logging the first one out."""
    await make_user(session, username="amina")
    first = await sign_in(client, "amina")
    second = await sign_in(client, "amina")
    assert first == second


async def test_a_wrong_password_is_rejected_in_the_shape_the_form_reads(
    client: httpx.AsyncClient, session
) -> None:
    await make_user(session, username="amina")
    response = await client.post(
        "/api/auth/login/", json={"username": "amina", "password": "wrong"}
    )
    assert response.status_code == 400
    body = response.json()
    assert body["non_field_errors"][0] == body["detail"]
    assert "credentials" in body["detail"]


async def test_an_unknown_username_gets_the_same_message_as_a_wrong_password(
    client: httpx.AsyncClient, session
) -> None:
    """Otherwise the response says which usernames exist."""
    await make_user(session, username="amina")
    unknown = await client.post("/api/auth/login/", json={"username": "ghost", "password": "x"})
    wrong = await client.post("/api/auth/login/", json={"username": "amina", "password": "x"})
    assert unknown.status_code == wrong.status_code == 400
    assert unknown.json() == wrong.json()


async def test_a_deactivated_user_cannot_sign_in(client: httpx.AsyncClient, session) -> None:
    await make_user(session, username="amina", is_active=False)
    response = await client.post(
        "/api/auth/login/", json={"username": "amina", "password": "correct-horse-battery"}
    )
    assert response.status_code == 400


async def test_signing_in_records_the_time(client: httpx.AsyncClient, session) -> None:
    user = await make_user(session, username="amina")
    assert user.last_login_at is None
    await sign_in(client, "amina")
    await session.refresh(user)
    assert user.last_login_at is not None


async def test_a_missing_field_is_one_readable_sentence(client: httpx.AsyncClient) -> None:
    """FastAPI's default is a list of objects, which the frontend prints as [object Object]."""
    response = await client.post("/api/auth/login/", json={"username": "amina"})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "password" in detail


async def test_signing_out_deletes_the_token(client: httpx.AsyncClient, session) -> None:
    await make_user(session, username="amina")
    token = await sign_in(client, "amina")

    response = await client.post("/api/auth/logout/", headers=auth(token))

    assert response.status_code == 204
    assert (await session.execute(select(AuthToken))).scalars().all() == []


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


async def test_an_unknown_token_is_401(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/auth/logout/", headers=auth("0" * 40))
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token."


async def test_the_wrong_scheme_is_401_rather_than_treated_as_anonymous(
    client: httpx.AsyncClient, session
) -> None:
    """A Bearer header is a caller trying to authenticate, not an anonymous one."""
    await make_user(session, username="amina")
    token = await sign_in(client, "amina")
    response = await client.post("/api/auth/logout/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_deleting_a_user_deletes_their_token(client: httpx.AsyncClient, session) -> None:
    user = await make_user(session, username="amina")
    await sign_in(client, "amina")
    await session.delete(user)
    await session.commit()
    assert (await session.execute(select(AuthToken))).scalars().all() == []
