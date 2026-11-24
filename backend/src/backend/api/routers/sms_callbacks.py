"""What the SMS gateway posts back: delivery reports, texts sent to the app, and numbers that
opted out through the gateway. Each URL carries `SMS_CALLBACK_SECRET`; a wrong or missing secret
gets 404. Sozuri's callbacks are also signed: a missing, malformed, stale or wrong signature
gets 401."""

import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, HTTPException, Request

from backend.api.deps import SessionDep
from backend.api.limits import check
from backend.config import get_settings
from backend.services import texting
from backend.services.errors import NotFound
from backend.services.ratelimit import RateLimit
from backend.services.sms import normalise_phone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms", tags=["sms"])

CALLBACKS = RateLimit(limit=6000, window=60)


class Unauthorized(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=401, detail=detail)


# How far a signature's timestamp may be from our clock (sozuri.net/docs/webhooks).
SIGNATURE_TOLERANCE_SECONDS = 300


def _check_secret(request: Request, secret: str) -> None:
    expected = get_settings().sms_callback_secret
    if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise NotFound("Not Found")
    check(CALLBACKS, request, "Too many callbacks; try later.")


def sozuri_signed(header: str, body: bytes, key: str, now: float | None = None) -> bool:
    """Whether `X-Sozuri-Signature` (t=<unix>,v1=<hex>) is HMAC-SHA256 of "t.body" under `key`,
    made within the tolerance."""
    parts = dict(item.split("=", 1) for item in header.split(",") if "=" in item)
    stamp, given = parts.get("t", ""), parts.get("v1", "")
    if not stamp.isdigit() or not given:
        return False
    if abs((now or time.time()) - int(stamp)) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(key.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, given)


async def _sozuri(request: Request, secret: str) -> dict:
    """The JSON body of a Sozuri callback that passes the URL secret (404 otherwise), then the
    signature, its age and the auth key (401 otherwise)."""
    _check_secret(request, secret)
    body = await request.body()
    settings = get_settings()
    key = settings.sozuri_signing_secret
    if not key or not sozuri_signed(request.headers.get("X-Sozuri-Signature", ""), body, key):
        raise Unauthorized("Bad signature.")
    try:
        payload = json.loads(body)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        return {}
    auth = settings.sozuri_auth_key
    if auth and not hmac.compare_digest(str(payload.get("authKey") or ""), auth):
        raise Unauthorized("Bad auth key.")
    return payload


async def _form(request: Request, secret: str) -> dict[str, str]:
    _check_secret(request, secret)
    form = await request.form()
    return {key: str(value) for key, value in form.items()}


@router.post("/{secret}/delivery/")
async def delivery_report(secret: str, request: Request, session: SessionDep) -> dict[str, bool]:
    """One text's delivery status; a repeat changes nothing."""
    form = await _form(request, secret)
    applied = await texting.apply_report(
        session, form.get("id", ""), form.get("status", ""), form.get("failureReason", "")
    )
    return {"applied": applied}


@router.post("/{secret}/inbound/")
async def inbound(secret: str, request: Request, session: SessionDep) -> dict[str, str]:
    """A text to the app's number; STOP opts the sender out."""
    form = await _form(request, secret)
    action = await texting.receive(
        session, form.get("id", ""), form.get("from", ""), form.get("to", ""), form.get("text", "")
    )
    return {"action": action}


@router.post("/{secret}/opt-out/")
async def gateway_opt_out(secret: str, request: Request, session: SessionDep) -> dict[str, bool]:
    """A number the gateway's own opt-out list now blocks."""
    form = await _form(request, secret)
    phone = normalise_phone(form.get("phoneNumber"))
    if phone is None:
        return {"applied": False}
    await texting.opt_out(session, phone, "gateway")
    await session.commit()
    return {"applied": True}


@router.post("/{secret}/sozuri/delivery/")
async def sozuri_delivery(secret: str, request: Request, session: SessionDep) -> dict[str, bool]:
    """One text's delivery status from Sozuri; a repeat changes nothing."""
    payload = await _sozuri(request, secret)
    applied = await texting.apply_report(
        session,
        str(payload.get("messageId") or ""),
        str(payload.get("status") or ""),
        "" if payload.get("status") == "success" else str(payload.get("status") or ""),
        provider="sozuri",
    )
    return {"applied": applied}


@router.post("/{secret}/sozuri/inbound/")
async def sozuri_inbound(secret: str, request: Request, session: SessionDep) -> dict[str, str]:
    """A text to the campaign's short code; STOP opts the sender out."""
    payload = await _sozuri(request, secret)
    action = await texting.receive(
        session,
        str(payload.get("messageId") or ""),
        str(payload.get("number") or ""),
        str(payload.get("shortcode") or ""),
        str(payload.get("message") or ""),
    )
    return {"action": action}
