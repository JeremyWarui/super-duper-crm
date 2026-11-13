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

from backend.models import CampaignMessage, PartyMessage, SmsInbound, SmsLog, SmsOptOut, User
from backend.services.errors import Refused
from backend.services.sms import Recipient, SendResult, get_sms_provider, normalise_phone

logger = logging.getLogger(__name__)

# Added to every text to supporters.
FOOTER = "\nReply STOP to opt out."
TEST_TEXT = "Test text from your campaign platform."

STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "END", "QUIT", "CANCEL", "ACHA"}

# The gateway's delivery report status, as this app records it.
REPORTED = {"Success": "delivered", "Failed": "failed", "Rejected": "failed"}
FINAL = {"delivered", "failed"}


def text_of(body: str) -> str:
    """What each person receives: the message and the opt-out line."""
    return body.strip() + FOOTER


async def decide(
    session: AsyncSession,
    model: type[CampaignMessage | PartyMessage],
    message: CampaignMessage | PartyMessage,
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
    """The fields a campaign or party message shows in its listing."""
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


def test_outcome(result: SendResult, number: str, practice: str) -> str:
    """What a test text did: `practice` when no gateway is set; Refused when it was not sent."""
    if result.provider == "console":
        return practice
    if not result.delivered:
        raise Refused(f"The text did not send: {result.detail or 'the gateway refused it'}")
    return f"Sent to {number}."


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
    party_message_id: uuid.UUID | None = None,
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
        result = await provider.send(numbers, body)
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

    def row(recipient: Recipient, status: str) -> SmsLog:
        provider_id = recipient.message_id if recipient.message_id not in ("", "None") else None
        return SmsLog(
            campaign_id=campaign_id,
            message_id=message_id,
            event_id=event_id,
            party_message_id=party_message_id,
            sender_id=sender.id if sender else None,
            purpose=purpose,
            phone=recipient.phone,
            body=body,
            provider=result.provider,
            provider_id=provider_id if status == "sent" else None,
            status=status,
            detail="" if status in ("sent", "practice") else recipient.detail or recipient.status,
        )

    taken = "practice" if result.provider == "console" else "sent"
    session.add_all([row(r, taken) for r in result.accepted])
    session.add_all([row(r, "failed") for r in result.rejected])
    return result, len(blocked)


async def apply_report(session: AsyncSession, provider_id: str, status: str, reason: str) -> bool:
    """Record the gateway's delivery report for one text; a repeat, or a report after the final
    one, changes nothing."""
    recorded = REPORTED.get(status)
    if not provider_id or recorded is None:
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
