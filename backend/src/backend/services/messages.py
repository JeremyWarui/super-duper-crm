"""Texts from a campaign to its supporters. Comms, Coordinators and the leads draft; only the
Candidate or Manager sends. A message goes to supporters who consented, have a number and have
not opted out, in the wards picked and inside the drafter's area."""

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_or_refuse
from backend.models import CampaignMessage, RegistrationCentre, SmsLog, Supporter, User, Ward
from backend.services import texting
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.permissions import Area
from backend.services.sms import normalise_all, parts_of


def text_of(body: str) -> str:
    """What each supporter receives: the message and the opt-out line."""
    return body.strip() + texting.FOOTER


async def _area_wards(session: AsyncSession, area: Area) -> set[uuid.UUID]:
    """The wards an area touches, whole or through one of its centres."""
    wards = set(area.wards)
    if area.centres:
        wards |= set(
            await session.scalars(
                select(RegistrationCentre.ward_id).where(RegistrationCentre.id.in_(area.centres))
            )
        )
    return wards


async def check_wards(session: AsyncSession, area: Area | None, wards: list[uuid.UUID]) -> None:
    if area is None or not wards:
        return
    outside = set(wards) - await _area_wards(session, area)
    if outside:
        raise Refused("Pick only wards inside your area.")


def _audience(campaign_id: uuid.UUID, area: Area | None, wards: list[uuid.UUID]) -> list:
    """The conditions on `supporters` for who a message may reach."""
    conditions = [
        Supporter.campaign_id == campaign_id,
        Supporter.consent_given.is_(True),
        Supporter.phone != "",
    ]
    if wards:
        conditions.append(Supporter.ward_id.in_(wards))
    if area is not None:
        conditions.append(area.where(Supporter.ward_id, Supporter.registration_centre_id))
    return conditions


async def recipients(
    session: AsyncSession, campaign_id: uuid.UUID, area: Area | None, wards: list[str | uuid.UUID]
) -> tuple[list[str], int, int]:
    """The numbers a message goes to now, how many opted out, and how many have no usable
    number."""
    ward_ids = [uuid.UUID(str(w)) for w in wards]
    phones = list(
        await session.scalars(
            select(Supporter.phone).where(*_audience(campaign_id, area, ward_ids))
        )
    )
    numbers, unusable = normalise_all(phones)
    blocked = await texting.opted_out(session, campaign_id, numbers)
    return [n for n in numbers if n not in blocked], len(blocked), len(unusable)


async def reach(
    session: AsyncSession, campaign_id: uuid.UUID, area: Area | None, wards: list, body: str
) -> dict:
    await check_wards(session, area, wards)
    numbers, blocked, unusable = await recipients(session, campaign_id, area, wards)
    text = text_of(body)
    return {
        "recipients": len(numbers),
        "opted_out": blocked,
        "no_number": unusable,
        "text": text,
        "parts": parts_of(text),
    }


async def addressable_wards(
    session: AsyncSession, campaign_id: uuid.UUID, area: Area | None
) -> list[dict]:
    """The wards the caller can text, with how many consenting supporters each has."""
    rows = await session.execute(
        select(Ward.id, Ward.name, func.count(Supporter.id))
        .select_from(Supporter)
        .join(Ward, Ward.id == Supporter.ward_id)
        .where(*_audience(campaign_id, area, []))
        .group_by(Ward.id, Ward.name)
        .order_by(Ward.name)
    )
    return [{"id": w, "name": n, "supporters": c} for w, n, c in rows]


async def draft(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    body: str,
    wards: list[uuid.UUID],
    area: Area | None,
    *,
    actor: User,
) -> CampaignMessage:
    await check_wards(session, area, wards)
    message = CampaignMessage(
        campaign_id=campaign_id,
        body=body.strip(),
        wards=[str(w) for w in dict.fromkeys(wards)],
        drafted_by_id=actor.id,
    )
    session.add(message)
    await session.flush()
    record(
        session,
        actor=actor,
        action="sms.draft",
        subject_type="campaign_message",
        subject_id=message.id,
        campaign_id=campaign_id,
        detail={"wards": message.wards},
    )
    await session.commit()
    return message


async def _decide(
    session: AsyncSession, message: CampaignMessage, status: str, actor: User, note: str = ""
) -> None:
    """Move a draft on, once; a second click finds it decided and is refused."""
    changed = await session.execute(
        update(CampaignMessage)
        .where(CampaignMessage.id == message.id, CampaignMessage.status == "draft")
        .values(status=status, decided_by_id=actor.id, decided_at=datetime.now(UTC), note=note)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount == 0:
        await session.rollback()
        raise Refused("That message is no longer a draft.")
    await session.refresh(message)


async def send(
    session: AsyncSession, message: CampaignMessage, drafter_area: Area | None, *, actor: User
) -> CampaignMessage:
    """Approve a draft and text it to its supporters, inside the drafter's area."""
    await _decide(session, message, "sent", actor)
    numbers, _, _ = await recipients(session, message.campaign_id, drafter_area, message.wards)
    result, _ = await texting.send(
        session,
        numbers,
        text_of(message.body),
        purpose="message",
        sender=actor,
        campaign_id=message.campaign_id,
        message_id=message.id,
    )
    message.recipients = len(result.accepted)
    record(
        session,
        actor=actor,
        action="sms.send",
        subject_type="campaign_message",
        subject_id=message.id,
        campaign_id=message.campaign_id,
        detail={
            "provider": result.provider,
            "accepted": len(result.accepted),
            "failed": len(result.rejected),
        },
    )
    await session.commit()
    return message


async def decline(
    session: AsyncSession, message: CampaignMessage, note: str, *, actor: User
) -> CampaignMessage:
    await _decide(session, message, "declined", actor, note.strip())
    record(
        session,
        actor=actor,
        action="sms.decline",
        subject_type="campaign_message",
        subject_id=message.id,
        campaign_id=message.campaign_id,
    )
    await session.commit()
    return message


async def discard(session: AsyncSession, message: CampaignMessage) -> None:
    if message.status != "draft":
        raise Refused("Only a draft can be deleted.")
    await session.delete(message)
    await session.commit()


async def get(session: AsyncSession, message_id: uuid.UUID) -> CampaignMessage:
    return await get_or_refuse(session, CampaignMessage, message_id, "message")


async def listing(
    session: AsyncSession, campaign_id: uuid.UUID, drafter: uuid.UUID | None, me: uuid.UUID
) -> list[dict]:
    """The campaign's messages, newest first, with how delivery went; `drafter` narrows them to
    one person's."""
    statement = select(CampaignMessage).where(CampaignMessage.campaign_id == campaign_id)
    if drafter is not None:
        statement = statement.where(CampaignMessage.drafted_by_id == drafter)
    messages = list(await session.scalars(statement.order_by(CampaignMessage.created_at.desc())))
    ids = [m.id for m in messages]
    counts: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    for message_id, status, n in await session.execute(
        select(SmsLog.message_id, SmsLog.status, func.count())
        .where(SmsLog.message_id.in_(ids))
        .group_by(SmsLog.message_id, SmsLog.status)
    ):
        counts[message_id][status] = n
    people = {m.drafted_by_id for m in messages} | {m.decided_by_id for m in messages}
    names = {
        u.id: u.display_name
        for u in await session.scalars(select(User).where(User.id.in_(people - {None})))
    }
    ward_ids = {uuid.UUID(w) for m in messages for w in m.wards}
    ward_names = {
        w.id: w.name for w in await session.scalars(select(Ward).where(Ward.id.in_(ward_ids)))
    }
    return [
        {
            "id": m.id,
            "body": m.body,
            "wards": m.wards,
            "ward_names": [ward_names.get(uuid.UUID(w), "") for w in m.wards],
            "status": m.status,
            "drafted_by": names.get(m.drafted_by_id, ""),
            "decided_by": names.get(m.decided_by_id, ""),
            "created_at": m.created_at,
            "decided_at": m.decided_at,
            "note": m.note,
            "recipients": m.recipients,
            "delivery": counts.get(m.id, {}),
            "mine": m.drafted_by_id == me,
        }
        for m in messages
    ]


async def log(session: AsyncSession, message: CampaignMessage) -> list[SmsLog]:
    return list(
        await session.scalars(
            select(SmsLog).where(SmsLog.message_id == message.id).order_by(SmsLog.phone)
        )
    )
