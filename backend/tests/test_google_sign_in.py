"""Google sign-in against a mocked Google: it signs in existing logins only, and is audited."""

import secrets
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey
from sqlalchemy import func, select

from backend.config import get_settings
from backend.models import AuditEvent, AuthToken, User, UserRole
from backend.services import oidc
from tests.factories import auth, make_user

CLIENT_ID = "test-client.apps.googleusercontent.com"
BIND = "the-page-bind-value"
KEY = RSAKey.generate_key(2048, parameters={"kid": "test-key"})
# Not Google's: a token it signs must be refused.
FORGER = RSAKey.generate_key(2048, parameters={"kid": "test-key"})


@pytest.fixture
def google(monkeypatch):
    """A Google that signs whatever claims the test sets for the next sign-in."""
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_client_secret", secrets.token_urlsafe(16))
    monkeypatch.setattr(oidc, "_metadata", {})
    claims: dict = {}
    seen: dict = {}

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
                    "token_endpoint": "https://oauth2.googleapis.com/token",
                    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
                },
            )
        if request.url.path == "/token":
            seen["form"] = parse_qs(request.content.decode())
            now = int(time.time())
            payload = {
                "iss": "https://accounts.google.com",
                "aud": CLIENT_ID,
                "sub": "1234567890",
                "iat": now,
                "exp": now + 300,
                "nonce": seen["nonce"],
                **claims,
            }
            token = jwt.encode({"alg": "RS256", "kid": "test-key"}, payload, seen.get("key", KEY))
            return httpx.Response(200, json={"id_token": token})
        return httpx.Response(200, json={"keys": [KEY.as_dict(private=False)]})

    monkeypatch.setattr(oidc, "transport", httpx.MockTransport(answer))
    return claims, seen


async def _sign_in_with_google(client, seen: dict) -> httpx.Response:
    """Start, come back from Google, and return the redirect to /signin."""
    start = await client.get("/api/auth/google/start/", params={"bind": BIND})
    assert start.status_code == 302, start.text
    query = parse_qs(urlparse(start.headers["location"]).query)
    seen["nonce"] = query["nonce"][0]
    seen["challenge"] = (query["code_challenge"][0], query["code_challenge_method"][0])
    back = await client.get(
        "/api/auth/google/callback/", params={"code": "c0de", "state": query["state"][0]}
    )
    assert back.status_code == 302
    return back


def _signin_query(response: httpx.Response) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(response.headers["location"]).query).items()}


async def test_a_verified_google_email_signs_in_its_login_and_is_audited(client, session, google):
    claims, seen = google
    await make_user(session, username="amina", email="amina@gmail.com")
    claims.update(email="amina@gmail.com", email_verified=True)

    handoff = _signin_query(await _sign_in_with_google(client, seen))["google"]
    elsewhere = await client.post(
        "/api/auth/google/finish/", json={"handoff": handoff, "bind": "another-page-value"}
    )
    finished = await client.post(
        "/api/auth/google/finish/", json={"handoff": handoff, "bind": BIND}
    )
    again = await client.post("/api/auth/google/finish/", json={"handoff": handoff, "bind": BIND})

    assert elsewhere.status_code == 400
    assert finished.status_code == 200, finished.text
    assert again.status_code == 400
    verifier = seen["form"]["code_verifier"][0]
    assert seen["challenge"] == (oidc.challenge(verifier), "S256")
    me = await client.get("/api/auth/me/", headers=auth(finished.json()["token"]))
    assert me.json()["username"] == "amina"
    actions = (await session.scalars(select(AuditEvent.action))).all()
    assert "login.google" in actions


async def test_an_unknown_google_email_is_refused_and_nothing_is_created(client, session, google):
    claims, seen = google
    claims.update(email="stranger@gmail.com", email_verified=True)
    before = await session.scalar(select(func.count()).select_from(User))

    refused = _signin_query(await _sign_in_with_google(client, seen))

    assert refused == {"google_error": "unknown"}
    assert await session.scalar(select(func.count()).select_from(User)) == before
    event = await session.scalar(
        select(AuditEvent).where(AuditEvent.action == "login.google_refused")
    )
    assert event.detail == {"reason": "unknown", "email": "stranger@gmail.com"}


@pytest.mark.parametrize("verified", [False, "false"])
async def test_an_unverified_google_email_is_refused(client, session, google, verified):
    claims, seen = google
    await make_user(session, username="amina", email="amina@gmail.com")
    claims.update(email="amina@gmail.com", email_verified=verified)

    assert _signin_query(await _sign_in_with_google(client, seen)) == {"google_error": "unverified"}
    assert await session.scalar(
        select(AuditEvent.id).where(AuditEvent.action == "login.google_refused")
    )
    assert await session.scalar(select(func.count()).select_from(AuthToken)) == 0


async def test_an_inactive_login_is_refused_through_google(client, session, google):
    claims, seen = google
    await make_user(session, username="amina", email="amina@gmail.com", is_active=False)
    claims.update(email="amina@gmail.com", email_verified=True)

    assert _signin_query(await _sign_in_with_google(client, seen)) == {"google_error": "unknown"}


async def test_a_token_not_signed_by_google_is_refused(client, session, google):
    claims, seen = google
    await make_user(session, username="amina", email="amina@gmail.com")
    claims.update(email="amina@gmail.com", email_verified=True)
    seen["key"] = FORGER

    assert _signin_query(await _sign_in_with_google(client, seen)) == {"google_error": "failed"}


async def test_a_callback_in_a_browser_that_did_not_start_is_refused(client, session, google):
    start = await client.get("/api/auth/google/start/", params={"bind": BIND})
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    client.cookies.clear()

    response = await client.get(
        "/api/auth/google/callback/", params={"code": "c0de", "state": state}
    )

    assert _signin_query(response) == {"google_error": "expired"}


async def test_google_answering_with_another_state_is_refused(client, session, google):
    assert (await client.get("/api/auth/google/start/", params={"bind": BIND})).status_code == 302

    response = await client.get(
        "/api/auth/google/callback/", params={"code": "c0de", "state": "forged"}
    )

    assert _signin_query(response) == {"google_error": "expired"}


@pytest.mark.parametrize(
    "bad",
    [
        {"nonce": "another-nonce"},
        {"aud": "someone-else.apps.googleusercontent.com"},
        {"iss": "https://evil.example"},
        {"exp": int(time.time()) - 60},
    ],
    ids=["nonce", "aud", "iss", "expired"],
)
async def test_an_identity_token_that_does_not_check_out_is_refused(client, session, google, bad):
    claims, seen = google
    await make_user(session, username="amina", email="amina@gmail.com")
    claims.update(email="amina@gmail.com", email_verified=True, **bad)

    assert _signin_query(await _sign_in_with_google(client, seen)) == {"google_error": "failed"}


async def test_google_sign_in_counts_as_2_step_for_the_superuser(client, session, google):
    claims, seen = google
    root = await make_user(session, username="root", role=UserRole.MANAGER, email="root@gmail.com")
    root.is_superuser = True
    await session.commit()
    claims.update(email="root@gmail.com", email_verified=True)

    handoff = _signin_query(await _sign_in_with_google(client, seen))["google"]
    token = (
        await client.post("/api/auth/google/finish/", json={"handoff": handoff, "bind": BIND})
    ).json()["token"]

    assert (await client.get("/api/admin/campaigns/", headers=auth(token))).status_code == 200
