"""Sending SMS. `SMS_PROVIDER` picks the provider; `console` records and sends nothing."""

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from backend.config import Settings, get_settings
from backend.services.errors import Refused

logger = logging.getLogger(__name__)

DEFAULT_COUNTRY_CODE = "254"
NATIONAL_NUMBER_LENGTH = 9

# Billed per part, per recipient; a long text is split into parts of 153.
SMS_PART_LENGTH = 160
SMS_LONG_PART_LENGTH = 153


def parts_of(message: str) -> int:
    """How many parts each recipient is billed for this text."""
    if not message:
        return 0
    if len(message) <= SMS_PART_LENGTH:
        return 1
    return (len(message) - 1) // SMS_LONG_PART_LENGTH + 1


@dataclass(frozen=True)
class Recipient:
    """One number and what the gateway made of it."""

    phone: str
    status: str
    detail: str = ""
    # The gateway's id for this text, which its delivery reports quote.
    message_id: str = ""


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
        return parts_of(self.message)


class SMSProvider(Protocol):
    """What the app knows about sending a message."""

    name: str

    async def send(
        self, recipients: list[str], message: str, idempotency_key: str | None = None
    ) -> SendResult: ...


_NON_DIGITS = re.compile(r"[^0-9+]")


def normalise_phone(raw: str | None, country_code: str = DEFAULT_COUNTRY_CODE) -> str | None:
    """A number as E.164 (from forms like `0712 345678`), or None."""
    if not raw:
        return None

    cleaned = _NON_DIGITS.sub("", raw.strip())
    if not cleaned:
        return None

    # A + is only meaningful at the front.
    if "+" in cleaned[1:]:
        return None
    plus, digits = cleaned.startswith("+"), cleaned.lstrip("+")
    if not (digits.isascii() and digits.isdigit()):
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


KENYAN_NUMBER = "Enter a Kenyan mobile number, like 0712 345678."


def require_phone(raw: str | None, refusal: str = KENYAN_NUMBER) -> str:
    """The number as E.164; Refused with `refusal` when it is not a phone number."""
    phone = normalise_phone(raw)
    if phone is None:
        raise Refused(refusal)
    return phone


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


class ConsoleSMSProvider:
    """Records the request and sends nothing."""

    name = "console"

    async def send(
        self, recipients: list[str], message: str, idempotency_key: str | None = None
    ) -> SendResult:
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
                "Set SMS_PROVIDER=sozuri with SOZURI_API_KEY, SOZURI_PROJECT and SOZURI_SENDER_ID "
                "to send."
            ),
        )


class AfricasTalkingSMSProvider:
    """Africa's Talking bulk SMS. Never run against the live gateway."""

    name = "africastalking"

    LIVE_URL = "https://api.africastalking.com/version1/messaging"
    SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
    TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        username: str,
        api_key: str,
        sender_id: str = "",
        sandbox: bool = False,
        transport=None,
    ):
        if not username or not api_key:
            raise ValueError(
                "Africa's Talking needs AT_USERNAME and AT_API_KEY. "
                "Leave SMS_PROVIDER=console until there is a subscription."
            )
        self.username = username
        self.api_key = api_key
        self.sender_id = sender_id
        self.transport = transport
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
                message_id=str(entry.get("messageId") or ""),
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

    async def send(
        self, recipients: list[str], message: str, idempotency_key: str | None = None
    ) -> SendResult:
        import httpx

        data, headers = self.build_request(recipients, message)
        async with httpx.AsyncClient(
            timeout=self.TIMEOUT_SECONDS, transport=self.transport
        ) as client:
            response = await client.post(self.url, data=data, headers=headers)
            response.raise_for_status()
            return self.parse_response(response.json(), message, len(recipients))


class SozuriSMSProvider:
    """Sozuri bulk SMS (sozuri.net/docs/text), in chunks of up to 500 numbers."""

    name = "sozuri"

    BASE = "https://sozuri.net/api"
    URL = f"{BASE}/v1/messaging"
    AUTHTEST_URL = f"{BASE}/v1/messaging/authtest"
    TIMEOUT_SECONDS = 30.0
    CHUNK = 500
    # v1 answers "sent" for a number it queued (v2 says "accepted").
    TAKEN = {"sent", "accepted", "scheduled"}

    def __init__(
        self,
        api_key: str,
        project: str,
        sender_id: str,
        message_type: str = "promotional",
        transport=None,
    ):
        if not (api_key and project and sender_id):
            raise ValueError("Sozuri needs SOZURI_API_KEY, SOZURI_PROJECT and SOZURI_SENDER_ID.")
        self.api_key = api_key
        self.project = project
        self.sender_id = sender_id
        self.message_type = message_type
        self.transport = transport

    def build_request(
        self, recipients: list[str], message: str, key: str | None = None
    ) -> tuple[dict, dict]:
        """JSON body and headers for one chunk; numbers go as 2547... without the plus. The same
        `key` on a repeat makes Sozuri answer with the first reply instead of sending again."""
        body = {
            "project": self.project,
            "from": self.sender_id,
            "to": ",".join(number.lstrip("+") for number in recipients),
            "message": message,
            "type": self.message_type,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Idempotency-Key": key or uuid.uuid4().hex,
        }
        return body, headers

    @classmethod
    def parse_response(cls, payload: dict, recipients: list[str]) -> tuple[list, list, str]:
        """Accepted and refused recipients for one chunk, and Sozuri's message.

        A refusal of the whole request (low balance, unregistered sender) comes back as HTTP 200
        with `messageData.message` starting "Error."; numbers it leaves out of `recipients`
        (opted out at the gateway) are refused.
        """
        note = str((payload.get("messageData") or {}).get("message") or "")
        accepted, rejected = [], []
        answered: set[str] = set()
        for entry in payload.get("recipients") or []:
            phone = normalise_phone(str(entry.get("to") or "")) or str(entry.get("to") or "")
            answered.add(phone)
            record = Recipient(
                phone=phone,
                status=str(entry.get("status") or "unknown"),
                detail=str(entry.get("statusCode") or ""),
                message_id=str(entry.get("messageId") or ""),
            )
            (accepted if record.status in cls.TAKEN else rejected).append(record)
        left_out = note or "Sozuri did not take this number."
        rejected += [
            Recipient(phone=n, status="not_sent", detail=left_out)
            for n in recipients
            if n not in answered
        ]
        return accepted, rejected, note

    async def check(self) -> tuple[bool, str]:
        """Whether Sozuri accepts the key and project; sends nothing."""
        import httpx

        async with httpx.AsyncClient(
            timeout=self.TIMEOUT_SECONDS, transport=self.transport
        ) as client:
            response = await client.get(
                self.AUTHTEST_URL,
                params={"project": self.project},
                headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
            )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        note = str(
            (payload.get("messageData") or {}).get("message") or payload.get("message") or ""
        )
        ok = response.status_code == 200 and note.startswith("Success")
        return ok, note or f"Sozuri answered {response.status_code}."

    async def send(
        self, recipients: list[str], message: str, idempotency_key: str | None = None
    ) -> SendResult:
        import httpx

        accepted: list[Recipient] = []
        rejected: list[Recipient] = []
        notes: list[str] = []
        async with httpx.AsyncClient(
            timeout=self.TIMEOUT_SECONDS, transport=self.transport
        ) as client:
            for start in range(0, len(recipients), self.CHUNK):
                chunk = recipients[start : start + self.CHUNK]
                key = (
                    None
                    if idempotency_key is None
                    else idempotency_key
                    if len(recipients) <= self.CHUNK
                    else f"{idempotency_key}-{start // self.CHUNK}"
                )
                body, headers = self.build_request(chunk, message, key)
                response = await client.post(self.URL, json=body, headers=headers)
                response.raise_for_status()
                taken, refused, note = self.parse_response(response.json(), chunk)
                accepted += taken
                rejected += refused
                if note:
                    notes.append(note)
        return SendResult(
            provider=self.name,
            delivered=bool(accepted),
            message=message,
            requested=len(recipients),
            accepted=accepted,
            rejected=rejected,
            detail="; ".join(dict.fromkeys(notes)),
        )


# Telkom Kenya mobile numbers (077x); Sozuri gets no delivery reports for them.
TELKOM_PREFIX = "+25477"
NO_REPORT = "no_report_expected"


def reports_delivery(provider: str, phone: str) -> bool:
    """Whether the gateway will send a delivery report for a text to this number."""
    return not (provider == "sozuri" and phone.startswith(TELKOM_PREFIX))


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
    if settings.sms_provider == "sozuri":
        return SozuriSMSProvider(
            api_key=settings.sozuri_api_key,
            project=settings.sozuri_project,
            sender_id=settings.sozuri_sender_id,
            message_type=settings.sozuri_message_type,
        )
    return ConsoleSMSProvider()
