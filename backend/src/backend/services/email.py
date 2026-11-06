"""Sending email. `EMAIL_PROVIDER` picks the provider; `practice` sends nothing.

Every email, sent or not, gets a row in `email_log`, with any secret in it blanked out.
"""

import asyncio
import logging
import smtplib
from collections import deque
from email.message import EmailMessage
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings, get_settings
from backend.models import EmailLog

logger = logging.getLogger(__name__)


class EmailProvider(Protocol):
    name: str

    async def send(self, to: str, subject: str, body: str) -> None:
        """Raises when the message did not leave."""


class PracticeEmailProvider:
    """Sends nothing: writes the whole email to the server log and keeps the last few here."""

    name = "practice"
    outbox: deque[tuple[str, str, str]] = deque(maxlen=50)

    async def send(self, to: str, subject: str, body: str) -> None:
        self.outbox.append((to, subject, body))
        logger.info("Practice email to %s: %s %s", to, subject, body)


class SmtpEmailProvider:
    """Any SMTP server, over STARTTLS, or implicit TLS on port 465."""

    name = "smtp"
    TIMEOUT_SECONDS = 20

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def message(self, to: str, subject: str, body: str) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = self.settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        return msg

    def _send(self, msg: EmailMessage) -> None:
        s = self.settings
        if s.smtp_port == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                s.smtp_host, s.smtp_port, timeout=self.TIMEOUT_SECONDS
            )
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=self.TIMEOUT_SECONDS)
            server.starttls()
        with server:
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)

    async def send(self, to: str, subject: str, body: str) -> None:
        await asyncio.to_thread(self._send, self.message(to, subject, body))


def get_email_provider(settings: Settings | None = None) -> EmailProvider:
    settings = settings or get_settings()
    if settings.email_provider == "smtp":
        return SmtpEmailProvider(settings)
    return PracticeEmailProvider()


async def send_email(
    session: AsyncSession, to: str, subject: str, body: str, *, secret: str = ""
) -> EmailLog:
    """Send one email and log it; a failed send is logged, not raised. The caller commits.

    `secret` (a sign-in token) goes to the recipient but never into `email_log`.
    """
    provider = get_email_provider()
    status, detail = ("practice" if provider.name == "practice" else "sent"), ""
    try:
        await provider.send(to, subject, body)
    except (OSError, smtplib.SMTPException) as exc:
        status, detail = "failed", str(exc)[:500]
        logger.warning("Email to %s failed: %s", to, exc)
    if secret:
        body = body.replace(secret, "[removed]")
    row = EmailLog(
        to=to, subject=subject, body=body, provider=provider.name, status=status, detail=detail
    )
    session.add(row)
    return row
