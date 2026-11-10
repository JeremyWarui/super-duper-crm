"""Paystack's HTTP API and its webhook signature, shared by money paid in and paid out."""

import hashlib
import hmac
import time

import httpx

from backend.config import get_settings

PAYSTACK_API = "https://api.paystack.co"
WEBHOOK_TOLERANCE = 300  # seconds a signed timestamp may be off


def body(response: httpx.Response) -> dict:
    """The JSON object Paystack answered with, or {} when it sent anything else."""
    try:
        found = response.json()
    except ValueError:
        return {}
    return found if isinstance(found, dict) else {}


class PaystackApi:
    """Calls Paystack with the secret key; `transport` lets tests answer in its place."""

    def __init__(self, secret_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._secret_key = secret_key
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=PAYSTACK_API,
            headers={"Authorization": f"Bearer {self._secret_key}"},
            timeout=20,
            transport=self._transport,
        )


def paystack_signed(raw: bytes, headers: dict[str, str], now: float | None = None) -> bool:
    """Whether a webhook body carries a valid Paystack signature.

    With a webhook secret, checks `Paystack-Signature` (HMAC-SHA512 of `t.body`, `t` within five
    minutes); without one, the older `x-paystack-signature` (HMAC-SHA512 of the body with the
    secret key).
    """
    settings = get_settings()
    if settings.paystack_webhook_secret:
        stamp, signatures = None, []
        for part in headers.get("paystack-signature", "").split(","):
            key, _, value = part.strip().partition("=")
            if key == "t" and value.isdigit() and stamp is None:
                stamp = value
            elif key == "v1":
                signatures.append(value.partition(":")[2])
        if stamp is None or abs((now or time.time()) - int(stamp)) > WEBHOOK_TOLERANCE:
            return False
        expected = hmac.new(
            settings.paystack_webhook_secret.encode(), stamp.encode() + b"." + raw, hashlib.sha512
        ).hexdigest()
        return any(hmac.compare_digest(expected, s) for s in signatures)
    if settings.paystack_secret_key:
        expected = hmac.new(settings.paystack_secret_key.encode(), raw, hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, headers.get("x-paystack-signature", ""))
    return False
