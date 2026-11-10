"""Google sign-in through OpenID Connect: the authorize link, the code exchange, and the checked
identity token."""

import base64
import hashlib
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from backend.config import get_settings

ISSUER = "https://accounts.google.com"
ISSUERS = [ISSUER, "accounts.google.com"]
DISCOVERY = f"{ISSUER}/.well-known/openid-configuration"
TIMEOUT_SECONDS = 10
METADATA_SECONDS = 3600

# Set by tests to answer as Google would.
transport: httpx.AsyncBaseTransport | None = None
_metadata: dict = {}


class OidcError(Exception):
    """Google's answer could not be trusted or used."""


@dataclass(frozen=True)
class Identity:
    email: str
    email_verified: bool
    subject: str


def configured() -> bool:
    settings = get_settings()
    return bool(settings.google_client_id and settings.google_client_secret)


def redirect_uri() -> str:
    return get_settings().url("/api/auth/google/callback/")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport)


async def metadata() -> dict:
    """Google's published endpoints, fetched once an hour."""
    if _metadata.get("fetched", 0) + METADATA_SECONDS < time.monotonic():
        async with _client() as client:
            response = await client.get(DISCOVERY)
        if response.status_code != 200:
            raise OidcError("Google's sign-in details could not be read.")
        _metadata.clear()
        _metadata.update(response.json(), fetched=time.monotonic())
    return _metadata


def challenge(verifier: str) -> str:
    """The PKCE S256 challenge for a code verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def authorize_url(state: str, nonce: str, verifier: str) -> str:
    query = {
        "response_type": "code",
        "client_id": get_settings().google_client_id,
        "redirect_uri": redirect_uri(),
        "scope": "openid email",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge(verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{(await metadata())['authorization_endpoint']}?{urlencode(query)}"


async def identity(code: str, nonce: str, verifier: str) -> Identity:
    """Trade the callback's code for an identity token and check its signature and claims."""
    settings = get_settings()
    found = await metadata()
    async with _client() as client:
        tokens = await client.post(
            found["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": redirect_uri(),
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
            },
        )
        if tokens.status_code != 200 or "id_token" not in tokens.json():
            raise OidcError("Google did not accept the sign-in.")
        keys = await client.get(found["jwks_uri"])
    if keys.status_code != 200:
        raise OidcError("Google's signing keys could not be read.")
    try:
        token = jwt.decode(
            tokens.json()["id_token"], KeySet.import_key_set(keys.json()), algorithms=["RS256"]
        )
        jwt.JWTClaimsRegistry(
            iss={"essential": True, "values": ISSUERS},
            aud={"essential": True, "value": settings.google_client_id},
            nonce={"essential": True, "value": nonce},
            exp={"essential": True},
            sub={"essential": True},
        ).validate(token.claims)
    except (JoseError, ValueError) as broken:
        raise OidcError("Google's identity token did not check out.") from broken
    claims = token.claims
    return Identity(
        email=str(claims.get("email", "")),
        email_verified=claims.get("email_verified") in (True, "true"),
        subject=str(claims["sub"]),
    )
