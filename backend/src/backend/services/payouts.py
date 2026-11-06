"""Sending a payment to a phone: practice mode, or M-Pesa transfers through Paystack."""

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx

from backend.config import get_settings
from backend.models import PaymentStatus


@dataclass
class PayoutResult:
    """PAID; SENDING when the provider confirms later; FAILED only if the money did not go.

    A provider that cannot tell raises instead, and the payment stays in SENDING for a person
    to resolve, so an unknown outcome is never retried into a second payment.
    """

    status: PaymentStatus
    reference: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Transfer:
    """One transfer as the provider records it; `reference` is the one this app sent."""

    reference: str
    status: str
    amount_kes: int
    code: str = ""


class BalanceUnavailable(Exception):
    """The provider did not say what the balance is."""


class PayoutProvider(Protocol):
    name: str
    moves_money: bool

    def fee_kes(self, amount_kes: int) -> int:
        """What the provider charges to send this amount."""
        ...

    async def balance_kes(self) -> int:
        """What can be sent now; raises BalanceUnavailable when the provider does not say."""
        ...

    async def transfers(self, since: datetime) -> list[Transfer] | None:
        """The provider's transfers since then; None when it keeps no record (practice)."""
        ...

    async def send(
        self, *, payment_id: uuid.UUID, reference: str, phone: str, name: str, amount_kes: int
    ) -> PayoutResult:
        """`reference` is unique to this attempt, so the provider can refuse a repeat of it."""
        ...


class PracticePayouts:
    """Moves no money: every payment is marked paid under a PRACTICE reference."""

    name = "practice"
    moves_money = False
    # A made-up balance, so the release form shows how a real one is used.
    DEMO_BALANCE_KES = 500_000

    def fee_kes(self, amount_kes: int) -> int:
        return 0

    async def balance_kes(self) -> int:
        return self.DEMO_BALANCE_KES

    async def transfers(self, since: datetime) -> list[Transfer] | None:
        return None

    async def send(
        self, *, payment_id: uuid.UUID, reference: str, phone: str, name: str, amount_kes: int
    ) -> PayoutResult:
        return PayoutResult(PaymentStatus.PAID, f"PRACTICE-{payment_id.hex[:10].upper()}")


def mpesa_fee_kes(amount_kes: int) -> int:
    """Paystack Kenya's fee for a transfer to an M-Pesa wallet (paystack.com/ke/pricing)."""
    if amount_kes <= 1_500:
        return 20
    if amount_kes <= 20_000:
        return 40
    return 60


PAYSTACK_API = "https://api.paystack.co"
# Transfer states that mean the money did not and will not go.
PAYSTACK_DEAD = {"failed", "reversed", "abandoned", "rejected", "blocked"}


def _body(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _message(response: httpx.Response) -> str:
    return str(_body(response).get("message") or "")[:150]


class PaystackPayouts:
    """M-Pesa transfers from the Paystack balance: a mobile money recipient, then a transfer.

    Every transfer Paystack accepts stays SENDING until its webhook says how it ended, so only
    the webhook marks a transfer paid.
    """

    name = "paystack"
    moves_money = True

    def __init__(self, secret_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._secret_key = secret_key
        self._transport = transport

    def fee_kes(self, amount_kes: int) -> int:
        return mpesa_fee_kes(amount_kes)

    async def balance_kes(self) -> int:
        try:
            async with self._client() as client:
                answer = await client.get("/balance")
        except httpx.HTTPError as exc:
            raise BalanceUnavailable("Paystack could not be reached.") from exc
        body = _body(answer)
        if answer.status_code >= 300 or not body.get("status"):
            raise BalanceUnavailable(f"Paystack refused: {_message(answer)}".rstrip(": "))
        for row in body.get("data") or []:
            if isinstance(row, dict) and row.get("currency") == "KES":
                return int(row.get("balance") or 0) // 100
        raise BalanceUnavailable("Paystack shows no KES balance.")

    async def transfers(self, since: datetime) -> list[Transfer] | None:
        found: list[Transfer] = []
        async with self._client() as client:
            for page in range(1, 51):
                answer = await client.get(
                    "/transfer",
                    params={"perPage": 100, "page": page, "from": since.date().isoformat()},
                )
                answer.raise_for_status()
                body = _body(answer)
                rows = body.get("data") or []
                for row in rows:
                    if isinstance(row, dict):
                        found.append(
                            Transfer(
                                reference=str(row.get("reference") or ""),
                                status=str(row.get("status") or ""),
                                amount_kes=int(row.get("amount") or 0) // 100,
                                code=str(row.get("transfer_code") or ""),
                            )
                        )
                meta = body.get("meta") or {}
                if len(rows) < 100 or page >= int(meta.get("pageCount") or page):
                    break
        return found

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=PAYSTACK_API,
            headers={"Authorization": f"Bearer {self._secret_key}"},
            timeout=20,
            transport=self._transport,
        )

    async def send(
        self, *, payment_id: uuid.UUID, reference: str, phone: str, name: str, amount_kes: int
    ) -> PayoutResult:
        async with self._client() as client:
            try:
                made = await client.post(
                    "/transferrecipient",
                    json={
                        "type": "mobile_money",
                        "name": name,
                        "account_number": phone.removeprefix("+"),
                        "bank_code": "MPESA",
                        "currency": "KES",
                    },
                )
            except httpx.HTTPError:
                # No transfer was asked for, so nothing can have moved.
                return PayoutResult(PaymentStatus.FAILED, detail="Paystack could not be reached.")
            if made.status_code >= 300 or not _body(made).get("status"):
                return PayoutResult(
                    PaymentStatus.FAILED,
                    detail=f"Paystack refused the recipient: {_message(made)}".rstrip(": "),
                )
            recipient = made.json()["data"]["recipient_code"]

            # From here a lost answer may hide a transfer that went: errors propagate.
            sent = await client.post(
                "/transfer",
                json={
                    "source": "balance",
                    "amount": amount_kes * 100,
                    "recipient": recipient,
                    "reference": reference,
                    "currency": "KES",
                    "reason": "Payment for work done",
                },
            )
        if sent.status_code >= 500:
            sent.raise_for_status()
        if 400 <= sent.status_code < 500 or (
            sent.status_code < 300 and not _body(sent).get("status")
        ):
            return PayoutResult(
                PaymentStatus.FAILED,
                detail=f"Paystack refused the transfer: {_message(sent)}".rstrip(": "),
            )
        data = sent.json()["data"]
        code = str(data.get("transfer_code") or "")
        state = str(data.get("status") or "")
        if state in PAYSTACK_DEAD:
            return PayoutResult(PaymentStatus.FAILED, code, f"Paystack says the transfer {state}.")
        return PayoutResult(PaymentStatus.SENDING, code)


def get_payout_provider() -> PayoutProvider:
    settings = get_settings()
    if settings.payout_provider == "paystack":
        return PaystackPayouts(settings.paystack_secret_key)
    return PracticePayouts()


WEBHOOK_TOLERANCE = 300  # seconds a signed timestamp may be off


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
