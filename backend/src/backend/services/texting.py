"""Every text the app sends goes through `send`: opted-out numbers are dropped, one `sms_log`
row is written per number, and the gateway's delivery reports and STOP replies come back here."""

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from backend.models import (
    CampaignMember,
    CampaignMessage,
    SmsInbound,
    SmsLog,
    SmsOptOut,
    Supporter,
    User,
)
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.sms import (
    NO_REPORT,
    Recipient,
    SendResult,
    get_sms_provider,
    normalise_phone,
    reports_delivery,
    require_phone,
)

logger = logging.getLogger(__name__)

# Added to every text to supporters.
FOOTER = "\nReply STOP to opt out."
TEST_TEXT = "Test text from your campaign platform."

STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "END", "QUIT", "CANCEL", "ACHA"}

# The gateway's delivery report status, as this app records it.
REPORTED = {"Success": "delivered", "Failed": "failed", "Rejected": "failed"}
# Sozuri delivery statuses (sozuri.net/docs/text); Airtel reports only success or failed.
SOZURI_REPORTED = {
    "success": "delivered",
    "failed": "failed",
    "network_failure": "failed",
    "delivery_impossible": "failed",
    "absent_subscriber": "failed",
    "unknown_error": "failed",
}
REPORTS = {"africastalking": REPORTED, "sozuri": SOZURI_REPORTED}
FINAL = {"delivered", "failed"}


def text_of(body: str) -> str:
    """What each person receives: the message and the opt-out line."""
    return body.strip() + FOOTER


async def decide(
    session: AsyncSession,
    model: type[CampaignMessage],
    message: CampaignMessage,
    status: str,
    actor: User,
    note: str = "",
) -> None:
    """Move a draft on, once; a second click finds it decided and is refused."""
    changed = await session.execute(
        update(model)
        .where(model.id == message.id, model.status == "draft")
        .values(status=status, decided_by_id=actor.id, decided_at=datetime.now(UTC), note=note)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount == 0:
        await session.rollback()
        raise Refused("That message is no longer a draft.")
    await session.refresh(message)


def send_detail(result: SendResult) -> dict:
    """The audit detail of a message sent."""
    return {
        "provider": result.provider,
        "accepted": len(result.accepted),
        "failed": len(result.rejected),
    }


async def delivery_counts(
    session: AsyncSession, column: InstrumentedAttribute, ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    """How many texts of each message are in each delivery status, by `column` of sms_log."""
    counts: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    for message_id, status, n in await session.execute(
        select(column, SmsLog.status, func.count())
        .where(column.in_(ids))
        .group_by(column, SmsLog.status)
    ):
        counts[message_id][status] = n
    return counts


def draft_row(message, names: dict, counts: dict, me: uuid.UUID) -> dict:
    """The fields a message shows in its listing."""
    return {
        "id": message.id,
        "body": message.body,
        "status": message.status,
        "drafted_by": names.get(message.drafted_by_id, ""),
        "decided_by": names.get(message.decided_by_id, ""),
        "created_at": message.created_at,
        "decided_at": message.decided_at,
        "note": message.note,
        "recipients": message.recipients,
        "delivery": counts.get(message.id, {}),
        "mine": message.drafted_by_id == me,
    }


async def names_of(session: AsyncSession, user_ids: set) -> dict[uuid.UUID, str]:
    """The display name of each login named."""
    return {
        u.id: u.display_name
        for u in await session.scalars(select(User).where(User.id.in_(user_ids - {None})))
    }


async def opted_out(
    session: AsyncSession, campaign_id: uuid.UUID | None, phones: list[str]
) -> set[str]:
    """The numbers here that asked this campaign, or the whole installation, for no texts."""
    if not phones:
        return set()
    scope = SmsOptOut.campaign_id.is_(None)
    if campaign_id is not None:
        scope = or_(scope, SmsOptOut.campaign_id == campaign_id)
    rows = await session.scalars(select(SmsOptOut.phone).where(SmsOptOut.phone.in_(phones), scope))
    return set(rows)


async def send_test(session: AsyncSession, number: str, *, actor: User) -> SendResult:
    """Text TEST_TEXT to one number; the caller audits and commits."""
    result, _ = await send(session, [number], TEST_TEXT, purpose="test", sender=actor)
    return result


NOT_OURS = (
    "Test texts go only to the campaign's own logins and to supporters who agreed to be texted."
)


async def campaign_test(
    session: AsyncSession, campaign_id: uuid.UUID, phone: str, body: str, *, actor: User
) -> str:
    """Text one number for the campaign, past the queue, and audit it; commits. With a live
    gateway the number must be a login of the campaign or a consenting supporter."""
    number = require_phone(phone)
    if get_sms_provider().name != "console":
        member = await session.scalar(
            select(User.id)
            .join(CampaignMember, CampaignMember.user_id == User.id)
            .where(CampaignMember.campaign_id == campaign_id, User.phone == number)
        )
        supporter = await session.scalar(
            select(Supporter.id).where(
                Supporter.campaign_id == campaign_id,
                Supporter.phone == number,
                Supporter.consent_given.is_(True),
                Supporter.sms_consent.is_(True),
            )
        )
        if member is None and supporter is None:
            raise Refused(NOT_OURS)
    result, _ = await send(
        session, [number], body.strip(), purpose="test", sender=actor, campaign_id=campaign_id
    )
    record(
        session,
        actor=actor,
        action="sms.test",
        subject_type="campaign",
        subject_id=campaign_id,
        campaign_id=campaign_id,
        detail={"delivered": result.delivered},
    )
    await session.commit()
    return test_outcome(result, number, "Practice mode: the text was logged, not sent.")


async def test_log(session: AsyncSession, campaign_id: uuid.UUID, limit: int = 20) -> list:
    """The campaign's latest test texts."""
    statement = (
        select(SmsLog)
        .where(SmsLog.campaign_id == campaign_id, SmsLog.purpose == "test")
        .order_by(SmsLog.created_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(statement)).all())


def test_outcome(result: SendResult, number: str, practice: str) -> str:
    """What a test text did: `practice` when no gateway is set; Refused when it was not sent."""
    if result.provider == "console":
        return practice
    if not result.delivered:
        raise Refused(f"The text did not send: {result.detail or 'the gateway refused it'}")
    return f"Sent to {number}."


def _detail(recipient: Recipient, status: str, provider: str) -> str:
    if status == "sent":
        return "" if reports_delivery(provider, recipient.phone) else NO_REPORT
    if status == "practice":
        return ""
    return recipient.detail or recipient.status


async def send(
    session: AsyncSession,
    phones: list[str],
    body: str,
    *,
    purpose: str,
    sender: User | None,
    campaign_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
) -> tuple[SendResult, int]:
    """Text these E.164 numbers, leaving out any that opted out; returns the gateway's answer and
    how many were left out. The caller commits."""
    blocked = await opted_out(session, campaign_id, phones)
    numbers = [p for p in phones if p not in blocked]
    provider = get_sms_provider()
    if not numbers:
        nobody = SendResult(
            provider=provider.name,
            delivered=False,
            message=body,
            requested=0,
            detail="Every number here opted out." if blocked else "Nobody left to text.",
        )
        return nobody, len(blocked)
    try:
        result, _ = await deliver(
            session,
            numbers,
            body,
            purpose=purpose,
            sender=sender,
            campaign_id=campaign_id,
            message_id=message_id,
            event_id=event_id,
            provider=provider,
        )
    except Exception as exc:
        logger.warning("sms send failed: %s", exc)
        refused = [Recipient(phone=n, status="failed", detail=str(exc)[:300]) for n in numbers]
        result = SendResult(
            provider=provider.name,
            delivered=False,
            message=body,
            requested=len(numbers),
            rejected=refused,
            detail="The gateway did not answer; nothing was sent.",
        )
        _log(session, result, purpose, sender, campaign_id, message_id, event_id)
    return result, len(blocked)


async def deliver(
    session: AsyncSession,
    numbers: list[str],
    body: str,
    *,
    purpose: str,
    sender: User | None,
    campaign_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
    provider=None,
    idempotency_key: str | None = None,
) -> tuple[SendResult, dict[str, SmsLog]]:
    """Hand these numbers to the gateway and log each one; returns its answer and the log row
    per number. A gateway that does not answer raises, and nothing is logged. The caller
    commits."""
    provider = provider or get_sms_provider()
    if idempotency_key is None:
        result = await provider.send(numbers, body)
    else:
        result = await provider.send(numbers, body, idempotency_key=idempotency_key)
    rows = _log(session, result, purpose, sender, campaign_id, message_id, event_id)
    return result, rows


def _log(
    session: AsyncSession,
    result: SendResult,
    purpose: str,
    sender: User | None,
    campaign_id: uuid.UUID | None,
    message_id: uuid.UUID | None,
    event_id: uuid.UUID | None,
) -> dict[str, SmsLog]:
    def row(recipient: Recipient, status: str) -> SmsLog:
        provider_id = recipient.message_id if recipient.message_id not in ("", "None") else None
        return SmsLog(
            campaign_id=campaign_id,
            message_id=message_id,
            event_id=event_id,
            sender_id=sender.id if sender else None,
            purpose=purpose,
            phone=recipient.phone,
            body=result.message,
            provider=result.provider,
            provider_id=provider_id if status == "sent" else None,
            status=status,
            detail=_detail(recipient, status, result.provider),
        )

    taken = "practice" if result.provider == "console" else "sent"
    rows = {r.phone: row(r, taken) for r in result.accepted}
    rows.update({r.phone: row(r, "failed") for r in result.rejected})
    session.add_all(rows.values())
    return rows


async def apply_report(
    session: AsyncSession,
    provider_id: str,
    status: str,
    reason: str,
    provider: str = "africastalking",
) -> bool:
    """Record the gateway's delivery report for one text; a repeat, an unknown status, or a report
    after the final one changes nothing."""
    recorded = REPORTS[provider].get(status)
    if not provider_id or recorded is None:
        if provider_id:
            logger.warning("%s delivery report with unknown status %r ignored", provider, status)
        return False
    changed = await session.execute(
        update(SmsLog)
        .where(SmsLog.provider_id == provider_id, SmsLog.status.not_in(FINAL))
        .values(status=recorded, detail=reason or "", updated_at=datetime.now(UTC))
    )
    await session.commit()
    return changed.rowcount > 0


async def opt_out(session: AsyncSession, phone: str, source: str) -> uuid.UUID | None:
    """Stop texting this number from the campaign that last texted it, or from the whole
    installation when no campaign has; returns that campaign. The caller commits."""
    campaign_id = await session.scalar(
        select(SmsLog.campaign_id)
        .where(SmsLog.phone == phone)
        .order_by(SmsLog.created_at.desc())
        .limit(1)
    )
    exists = await session.scalar(
        select(SmsOptOut.id).where(
            SmsOptOut.phone == phone,
            SmsOptOut.campaign_id.is_(None)
            if campaign_id is None
            else SmsOptOut.campaign_id == campaign_id,
        )
    )
    if exists is None:
        try:
            async with session.begin_nested():
                session.add(SmsOptOut(phone=phone, campaign_id=campaign_id, source=source))
        except IntegrityError:
            pass
    return campaign_id


async def receive(session: AsyncSession, provider_id: str, sender: str, to: str, body: str) -> str:
    """Keep a text sent to the app once per gateway id; a STOP opts the number out."""
    if not provider_id:
        return "ignored"
    if await session.scalar(select(SmsInbound.id).where(SmsInbound.provider_id == provider_id)):
        return "repeat"
    phone = normalise_phone(sender) or sender[:20]
    words = body.strip().upper().split()
    action = "opted_out" if words and words[0].strip(".!") in STOP_WORDS else "none"
    try:
        async with session.begin_nested():
            session.add(
                SmsInbound(
                    provider_id=provider_id[:100],
                    phone=phone,
                    to=to[:20],
                    body=body[:1000],
                    action=action,
                )
            )
    except IntegrityError:
        return "repeat"
    if action == "opted_out" and normalise_phone(sender):
        await opt_out(session, phone, "stop")
    await session.commit()
    return action
