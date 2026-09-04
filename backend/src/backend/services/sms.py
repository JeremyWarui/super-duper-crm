"""Sending SMS, behind one interface with two providers.

The campaign sends invitations to supporters' phones. Africa's Talking is the
gateway that would carry them, and there is no subscription yet, so the default
provider records what it was asked to send and reports that nothing left the
building. Everything above this module is written against `SMSProvider` and
does not know which one is in use; switching is a setting, not a code change.

    SMS_PROVIDER=console          # the default: records, never sends
    SMS_PROVIDER=africastalking   # needs AT_USERNAME and AT_API_KEY

The recipient list is normalised to E.164 first, because a register filled in
by hand holds `0712 345678`, `+254712345678` and `254-712-345-678` for the same
person, and a gateway bills for each one it accepts.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Kenya. The country this is built for, and the only one the register holds.
DEFAULT_COUNTRY_CODE = "254"
NATIONAL_NUMBER_LENGTH = 9

# Africa's Talking counts a message in 160-character parts, and bills per part.
SMS_PART_LENGTH = 160


@dataclass(frozen=True)
class Recipient:
    """One phone number, and what the gateway made of it."""

    phone: str
    status: str
    detail: str = ""


@dataclass
class SendResult:
    """What one send attempt did.

    `delivered` is False whenever nothing actually left, which is the normal
    case until there is a subscription. Callers show it rather than assuming.
    """

    provider: str
    delivered: bool
    message: str
    requested: int
    accepted: list[Recipient] = field(default_factory=list)
    rejected: list[Recipient] = field(default_factory=list)
    detail: str = ""

    @property
    def parts(self) -> int:
        """How many 160-character parts each recipient would be billed."""
        if not self.message:
            return 0
        return (len(self.message) - 1) // SMS_PART_LENGTH + 1


class SMSProvider(Protocol):
    """What the rest of the app is allowed to know about sending a message."""

    name: str

    async def send(self, recipients: list[str], message: str) -> SendResult: ...


# ------------------------------------------------------------------- numbers

_NON_DIGITS = re.compile(r"[^\d+]")


def normalise_phone(raw: str | None, country_code: str = DEFAULT_COUNTRY_CODE) -> str | None:
    """A number as E.164, or None when it cannot be one.

    Accepts what people actually type: `0712 345678`, `+254 712 345 678`,
    `254-712-345678`, `712345678`. Returns `+254712345678` for all of them.
    Anything left over is rejected rather than guessed at, because a wrong
    number is a message delivered to a stranger.
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
    """Split a register's phone column into numbers worth sending to, and the rest.

    Duplicates collapse: one person listed twice is one message, billed once.
    """
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
    """Records the request and sends nothing.

    The default, and what runs until there is an Africa's Talking subscription.
    It reports `delivered=False` so no screen can claim a message went out.
    """

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
    """Sends through Africa's Talking.

    Built to their bulk SMS endpoint: a form post carrying `username`, `to` as
    a comma-separated list, and `message`, authenticated by an `apiKey` header.
    Their reply carries one recipient object per number with a `status` of
    `Success` or a reason it was not taken.

    Untested against the live gateway: there is no subscription yet. The
    request shape and the parsing are covered against recorded responses, so
    what remains unproven is the network call itself.
    """

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
        # Their sandbox only accepts the literal username "sandbox".
        self.url = self.SANDBOX_URL if sandbox or username == "sandbox" else self.LIVE_URL

    def build_request(self, recipients: list[str], message: str) -> tuple[dict, dict]:
        """The form fields and headers for one send. Separated so it is testable."""
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
        """Their reply, split into what they took and what they would not."""
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
