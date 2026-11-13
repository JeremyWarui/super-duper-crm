"""What Africa's Talking posts back: delivery reports, texts sent to the app, and numbers that
opted out through the gateway. It does not sign callbacks, so each URL carries
`SMS_CALLBACK_SECRET`; a wrong or missing secret gets 404."""

import hmac
import logging

from fastapi import APIRouter, Request

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


async def _form(request: Request, secret: str) -> dict[str, str]:
    expected = get_settings().sms_callback_secret
    if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise NotFound("Not Found")
    check(CALLBACKS, request, "Too many callbacks; try later.")
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
