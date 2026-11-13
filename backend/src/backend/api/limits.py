"""The per-device rate limits on public forms, as the routes apply them."""

import ipaddress
import os

from fastapi import HTTPException, Request, status

from backend.services.ratelimit import RateLimit

TOO_MANY = "Too many tries; try later."
TOO_MANY_SIGNUPS = "Too many sign-ups from this device; try later."


def client_key(request: Request) -> str:
    """Who is sending, for a rate limit: the address Fly saw, or the connection's own.

    An IPv6 client is keyed by its /64, which one device can roam within.
    """
    raw = request.headers.get("fly-client-ip") if os.environ.get("FLY_APP_NAME") else None
    raw = raw or (request.client.host if request.client else "")
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return raw
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def check(limit: RateLimit, request: Request, message: str = TOO_MANY) -> None:
    """Count this request against `limit`; 429 with `message` once it is used up."""
    if not limit.allow(client_key(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, message)
