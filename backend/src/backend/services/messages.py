"""Texts from a campaign to its supporters. Comms, Coordinators and the leads draft; only the
Candidate or Manager sends. A message goes to supporters who opted in to texts, have a number and
have not opted out, at the support levels and in the wards picked, inside the drafter's area."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.db.session import get_or_refuse
from backend.models import (
    CampaignMessage,
    Event,
    RegistrationCentre,
    SmsLog,
    Supporter,
    SupportLevel,
    User,
    Ward,
)
from backend.services import sms_queue, texting
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.permissions import Area
from backend.services.sms import normalise_all, parts_of


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


def _audience(
    campaign_id: uuid.UUID,
    area: Area | None,
    wards: list[uuid.UUID],
    *,
    with_phone: bool = True,
    consenting: bool = True,
    levels: list | None = None,
) -> list:
    """The conditions on `supporters` for who a text may reach; `with_phone` drops the ones
    with no number at all, `consenting=False` keeps those who did not opt in to texts, and
    `levels` keeps those support levels (none given keeps every level)."""
    conditions = [Supporter.campaign_id == campaign_id]
    if consenting:
        conditions += [Supporter.consent_given.is_(True), Supporter.sms_consent.is_(True)]
    if levels:
        conditions.append(Supporter.support_level.in_(levels))
    if with_phone:
        conditions.append(Supporter.phone != "")
    if wards:
        conditions.append(Supporter.ward_id.in_(wards))
    if area is not None:
        conditions.append(area.where(Supporter.ward_id, Supporter.registration_centre_id))
    return conditions


async def recipients(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    area: Area | None,
    wards: list[str | uuid.UUID],
    levels: list | None = None,
) -> tuple[list[str], int, int]:
    """The numbers a message goes to now, how many opted out, and how many have no usable
    number."""
    ward_ids = [uuid.UUID(str(w)) for w in wards]
    phones = list(
        await session.scalars(
            select(Supporter.phone).where(*_audience(campaign_id, area, ward_ids, levels=levels))
        )
    )
    numbers, unusable = normalise_all(phones)
    blocked = await texting.opted_out(session, campaign_id, numbers)
    return [n for n in numbers if n not in blocked], len(blocked), len(unusable)


def invite_audience(
    event: Event, area: Area | None, *, whole_campaign: bool, support_levels: list
) -> list:
    """The conditions on `supporters` for everyone an event invite is addressed to, consenting or
    not: the event's ward, or the whole campaign, inside the caller's area."""
    conditions = _audience(event.campaign_id, area, [], with_phone=False, consenting=False)
    if not whole_campaign:
        conditions.append(Supporter.ward_id == event.ward_id)
    if support_levels:
        conditions.append(Supporter.support_level.in_(support_levels))
    return conditions


async def reach(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    area: Area | None,
    wards: list,
    body: str,
    levels: list | None = None,
) -> dict:
    """Who the text would reach now, the text they get and what sending it would cost."""
    await check_wards(session, area, wards)
    numbers, blocked, unusable = await recipients(session, campaign_id, area, wards, levels)
    text = texting.text_of(body)
    parts = parts_of(text)
    return {
        "recipients": len(numbers),
        "opted_out": blocked,
        "no_number": unusable,
        "text": text,
        "parts": parts,
        "estimated_cost_cents": len(numbers) * parts * get_settings().sms_part_price_cents,
    }


async def addressable_wards(
    session: AsyncSession, campaign_id: uuid.UUID, area: Area | None
) -> list[dict]:
    """The wards the caller can text, with how many contacts in each opted in to texts."""
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
    language: str = "en",
    levels: list | None = None,
) -> CampaignMessage:
    await check_wards(session, area, wards)
    message = CampaignMessage(
        campaign_id=campaign_id,
        body=body.strip(),
        language=language,
        wards=[str(w) for w in dict.fromkeys(wards)],
        support_levels=[str(level) for level in dict.fromkeys(levels or [])],
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
        detail={"wards": message.wards, "support_levels": message.support_levels},
    )
    await session.commit()
    return message


async def send(
    session: AsyncSession,
    message: CampaignMessage,
    drafter_area: Area | None,
    *,
    actor: User,
    language: str | None = None,
) -> CampaignMessage:
    """Approve a draft: it passes the compliance gate and goes out as a run, inside the
    drafter's area (`services/sms_queue.py`)."""
    wards = [uuid.UUID(str(w)) for w in message.wards]
    audience = _audience(
        message.campaign_id,
        drafter_area,
        wards,
        consenting=False,
        levels=[SupportLevel(level) for level in message.support_levels or []],
    )
    await sms_queue.approve(
        session, message, audience, language=language or message.language, actor=actor
    )
    record(
        session,
        actor=actor,
        action="sms.send",
        subject_type="campaign_message",
        subject_id=message.id,
        campaign_id=message.campaign_id,
        detail={"recipients": message.recipients},
    )
    await session.commit()
    return message


async def decline(
    session: AsyncSession, message: CampaignMessage, note: str, *, actor: User
) -> CampaignMessage:
    await texting.decide(session, CampaignMessage, message, "declined", actor, note.strip())
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
    session: AsyncSession,
    campaign_id: uuid.UUID,
    drafter: uuid.UUID | None,
    me: uuid.UUID,
    ids: list[uuid.UUID] | None = None,
) -> list[dict]:
    """The campaign's messages, newest first, with how delivery went; `drafter` narrows them to
    one person's, `ids` to those messages."""
    statement = select(CampaignMessage).where(CampaignMessage.campaign_id == campaign_id)
    if drafter is not None:
        statement = statement.where(CampaignMessage.drafted_by_id == drafter)
    if ids is not None:
        statement = statement.where(CampaignMessage.id.in_(ids))
    messages = list(await session.scalars(statement.order_by(CampaignMessage.created_at.desc())))
    counts = await texting.delivery_counts(session, SmsLog.message_id, [m.id for m in messages])
    names = await texting.names_of(
        session, {m.drafted_by_id for m in messages} | {m.decided_by_id for m in messages}
    )
    ward_ids = {uuid.UUID(w) for m in messages for w in m.wards}
    ward_names = {
        w.id: w.name for w in await session.scalars(select(Ward).where(Ward.id.in_(ward_ids)))
    }
    return [
        texting.draft_row(m, names, counts, me)
        | {
            "wards": m.wards,
            "ward_names": [ward_names.get(uuid.UUID(w), "") for w in m.wards],
            "support_levels": list(m.support_levels or []),
            "language": m.language,
        }
        for m in messages
    ]


async def log(session: AsyncSession, message: CampaignMessage) -> list[SmsLog]:
    return list(
        await session.scalars(
            select(SmsLog).where(SmsLog.message_id == message.id).order_by(SmsLog.phone)
        )
    )
