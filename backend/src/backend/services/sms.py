"""Sending SMS. `SMS_PROVIDER` picks the provider; `console` records and sends nothing."""

import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)

DEFAULT_COUNTRY_CODE = "254"
NATIONAL_NUMBER_LENGTH = 9

# Billed per part, per recipient.
SMS_PART_LENGTH = 160


@dataclass(frozen=True)
class Recipient:
    """One number and what the gateway made of it."""

    phone: str
    status: str
    detail: str = ""


@dataclass
class SendResult:
    """`delivered` is False whenever nothing left."""

    provider: str
    delivered: bool
    message: str
    requested: int
    accepted: list[Recipient] = field(default_factory=list)
    rejected: list[Recipient] = field(default_factory=list)
    detail: str = ""

    @property
    def parts(self) -> int:
        """Parts each recipient is billed."""
        if not self.message:
            return 0
        return (len(self.message) - 1) // SMS_PART_LENGTH + 1


class SMSProvider(Protocol):
    """What the app knows about sending a message."""

    name: str

    async def send(self, recipients: list[str], message: str) -> SendResult: ...


# ------------------------------------------------------------------- numbers

_NON_DIGITS = re.compile(r"[^\d+]")


def normalise_phone(raw: str | None, country_code: str = DEFAULT_COUNTRY_CODE) -> str | None:
    """A number as E.164, or None when it cannot be one.

    Accepts `0712 345678`, `+254 712 345 678`, `254-712-345678`, `712345678`.
    """
    if not raw:
        return None

    cleaned = _NON_DIGITS.sub("", raw.strip())
    if not cleaned:
        return None

    # A + is only meaningful at the front.
    if "+" in cleaned[1:]:
        return None
    plus, digits = cleaned.startswith("+"), cleaned.lstrip("+")
    if not digits.isdigit():
        return None

    if plus or digits.startswith(country_code):
        national = digits.removeprefix(country_code)
    elif digits.startswith("0"):
        national = digits[1:]
    else:
        national = digits

    if len(national) != NATIONAL_NUMBER_LENGTH or national.startswith("0"):
        return None
    return f"+{country_code}{national}"


def normalise_all(raw_numbers: list[str | None]) -> tuple[list[str], list[Recipient]]:
    """Usable numbers and the rest. Duplicates collapse to one."""
    keep: list[str] = []
    seen: set[str] = set()
    rejected: list[Recipient] = []

    for raw in raw_numbers:
        number = normalise_phone(raw)
        if number is None:
            rejected.append(
                Recipient(phone=(raw or ""), status="invalid", detail="Not a usable number.")
            )
            continue
        if number in seen:
            continue
        seen.add(number)
        keep.append(number)

    return keep, rejected


# ----------------------------------------------------------------- providers


class ConsoleSMSProvider:
    """Records the request and sends nothing."""

    name = "console"

    async def send(self, recipients: list[str], message: str) -> SendResult:
        logger.info(
            "sms not sent (no gateway configured): %d recipient(s), %d character(s)",
            len(recipients),
            len(message),
        )
        return SendResult(
            provider=self.name,
            delivered=False,
            message=message,
            requested=len(recipients),
            accepted=[Recipient(phone=number, status="skipped") for number in recipients],
            detail=(
                "No SMS gateway is configured, so nothing was sent. "
                "Set SMS_PROVIDER=africastalking with AT_USERNAME and AT_API_KEY to send."
            ),
        )


class AfricasTalkingSMSProvider:
    """Africa's Talking bulk SMS. Never run against the live gateway."""

    name = "africastalking"

    LIVE_URL = "https://api.africastalking.com/version1/messaging"
    SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
    TIMEOUT_SECONDS = 30.0

    def __init__(self, username: str, api_key: str, sender_id: str = "", sandbox: bool = False):
        if not username or not api_key:
            raise ValueError(
                "Africa's Talking needs AT_USERNAME and AT_API_KEY. "
                "Leave SMS_PROVIDER=console until there is a subscription."
            )
        self.username = username
        self.api_key = api_key
        self.sender_id = sender_id
        # Their sandbox only answers to the username "sandbox".
        self.url = self.SANDBOX_URL if sandbox or username == "sandbox" else self.LIVE_URL

    def build_request(self, recipients: list[str], message: str) -> tuple[dict, dict]:
        """Form fields and headers for one send."""
        data = {"username": self.username, "to": ",".join(recipients), "message": message}
        if self.sender_id:
            data["from"] = self.sender_id
        headers = {
            "apiKey": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        return data, headers

    @staticmethod
    def parse_response(payload: dict, message: str, requested: int) -> SendResult:
        """Their reply, split into taken and refused."""
        recipients = payload.get("SMSMessageData", {}).get("Recipients", []) or []
        accepted, rejected = [], []
        for entry in recipients:
            record = Recipient(
                phone=entry.get("number", ""),
                status=entry.get("status", "unknown"),
                detail=str(entry.get("statusCode", "")),
            )
            (accepted if record.status == "Success" else rejected).append(record)

        return SendResult(
            provider="africastalking",
            delivered=bool(accepted),
            message=message,
            requested=requested,
            accepted=accepted,
            rejected=rejected,
            detail=payload.get("SMSMessageData", {}).get("Message", ""),
        )

    async def send(self, recipients: list[str], message: str) -> SendResult:
        import httpx

        data, headers = self.build_request(recipients, message)
        async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
            response = await client.post(self.url, data=data, headers=headers)
            response.raise_for_status()
            return self.parse_response(response.json(), message, len(recipients))


def get_sms_provider(settings: Settings | None = None) -> SMSProvider:
    """The provider the settings ask for."""
    settings = settings or get_settings()
    if settings.sms_provider == "africastalking":
        return AfricasTalkingSMSProvider(
            username=settings.at_username,
            api_key=settings.at_api_key,
            sender_id=settings.at_sender_id,
            sandbox=settings.at_sandbox,
        )
    return ConsoleSMSProvider()
