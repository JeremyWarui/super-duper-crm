"""Party texts to its own members and volunteers: the Comms Officer drafts, the Party Super
Admin sends or declines, and only people whose consent covers SMS receive one.

Members get a text only if they ticked the join form's SMS box; volunteers only if they chose
SMS as the way to reach them. A STOP reply opts the number out of party texts.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Constituency,
    ContactMethod,
    County,
    PartyMember,
    PartyMemberStatus,
    PartyMessage,
    SmsLog,
    User,
    VolunteerProfile,
    VolunteerStatus,
    Ward,
)
from backend.services import texting
from backend.services.audit import record
from backend.services.errors import NotFound, Refused
from backend.services.sms import normalise_all

AUDIENCES = ("members", "volunteers")


def text_of(body: str) -> str:
    """What each person receives: the message and the opt-out line."""
    return body.strip() + texting.FOOTER


def _who(
    audience: str,
    county_id: uuid.UUID | None,
    constituency_id: uuid.UUID | None,
    ward_id: uuid.UUID | None,
):
    if audience == "members":
        model = PartyMember
        statement = select(PartyMember.phone).where(
            PartyMember.status == PartyMemberStatus.APPROVED,
            PartyMember.sms_consent_at.is_not(None),
        )
    else:
        model = VolunteerProfile
        statement = select(VolunteerProfile.phone).where(
            VolunteerProfile.campaign_id.is_(None),
            VolunteerProfile.status == VolunteerStatus.ACTIVE,
            VolunteerProfile.preferred_contact == ContactMethod.SMS,
        )
    if ward_id is not None:
        statement = statement.where(model.ward_id == ward_id)
    elif constituency_id is not None:
        statement = statement.join(Ward, Ward.id == model.ward_id).where(
            Ward.constituency_id == constituency_id
        )
    elif county_id is not None:
        statement = (
            statement.join(Ward, Ward.id == model.ward_id)
            .join(Constituency, Constituency.id == Ward.constituency_id)
            .where(Constituency.county_id == county_id)
        )
    return statement


async def recipients(
    session: AsyncSession,
    audience: str,
    county_id: uuid.UUID | None,
    constituency_id: uuid.UUID | None,
    ward_id: uuid.UUID | None,
) -> tuple[list[str], int]:
    """The numbers a message goes to now, and how many opted out."""
    numbers, _ = normalise_all(
        list(await session.scalars(_who(audience, county_id, constituency_id, ward_id)))
    )
    blocked = await texting.opted_out(session, None, numbers)
    return [n for n in numbers if n not in blocked], len(blocked)


async def _check_place(
    session: AsyncSession,
    county_id: uuid.UUID | None,
    constituency_id: uuid.UUID | None,
    ward_id: uuid.UUID | None,
) -> None:
    if constituency_id is not None:
        county = await session.scalar(
            select(Constituency.county_id).where(Constituency.id == constituency_id)
        )
        if county is None or (county_id is not None and county != county_id):
            raise Refused("That constituency is not in the county chosen.")
    if ward_id is None:
        return
    found = (
        await session.execute(
            select(Ward.constituency_id, Constituency.county_id)
            .join(Constituency, Constituency.id == Ward.constituency_id)
            .where(Ward.id == ward_id)
        )
    ).first()
    if found is None or (county_id is not None and found.county_id != county_id):
        raise Refused("That ward is not in the county chosen.")
    if constituency_id is not None and found.constituency_id != constituency_id:
        raise Refused("That ward is not in the constituency chosen.")


async def preview(
    session: AsyncSession,
    audience: str,
    county_id: uuid.UUID | None,
    constituency_id: uuid.UUID | None,
    ward_id: uuid.UUID | None,
) -> dict:
    await _check_place(session, county_id, constituency_id, ward_id)
    numbers, blocked = await recipients(session, audience, county_id, constituency_id, ward_id)
    return {"recipients": len(numbers), "opted_out": blocked}


async def draft(
    session: AsyncSession,
    *,
    body: str,
    audience: str,
    county_id: uuid.UUID | None,
    constituency_id: uuid.UUID | None,
    ward_id: uuid.UUID | None,
    actor: User,
) -> PartyMessage:
    await _check_place(session, county_id, constituency_id, ward_id)
    numbers, _ = await recipients(session, audience, county_id, constituency_id, ward_id)
    message = PartyMessage(
        body=body.strip(),
        audience=audience,
        county_id=county_id,
        constituency_id=constituency_id,
        ward_id=ward_id,
        drafted_by_id=actor.id,
        targeted=len(numbers),
    )
    session.add(message)
    await session.flush()
    record(
        session,
        actor=actor,
        action="party_sms.draft",
        subject_type="party_message",
        subject_id=message.id,
        detail={"audience": audience, "targeted": len(numbers)},
    )
    await session.commit()
    return message


async def get(session: AsyncSession, message_id: uuid.UUID) -> PartyMessage:
    message = await session.get(PartyMessage, message_id)
    if message is None:
        raise NotFound("No such message.")
    return message


async def _decide(
    session: AsyncSession, message: PartyMessage, status: str, actor: User, note: str = ""
) -> None:
    """Move a draft on once, never by whoever drafted it."""
    if message.drafted_by_id == actor.id:
        raise Refused("Someone other than whoever drafted the message approves it.")
    changed = await session.execute(
        update(PartyMessage)
        .where(PartyMessage.id == message.id, PartyMessage.status == "draft")
        .values(status=status, decided_by_id=actor.id, decided_at=datetime.now(UTC), note=note)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount == 0:
        await session.rollback()
        raise Refused("That message is no longer a draft.")
    await session.refresh(message)


async def send(session: AsyncSession, message: PartyMessage, *, actor: User) -> PartyMessage:
    """Approve a draft and text it to whoever its audience holds now."""
    await _decide(session, message, "sent", actor)
    numbers, _ = await recipients(
        session, message.audience, message.county_id, message.constituency_id, message.ward_id
    )
    result, _ = await texting.send(
        session,
        numbers,
        text_of(message.body),
        purpose="party",
        sender=actor,
        party_message_id=message.id,
    )
    message.recipients = len(result.accepted)
    record(
        session,
        actor=actor,
        action="party_sms.send",
        subject_type="party_message",
        subject_id=message.id,
        detail={
            "provider": result.provider,
            "accepted": len(result.accepted),
            "failed": len(result.rejected),
        },
    )
    await session.commit()
    return message


async def decline(
    session: AsyncSession, message: PartyMessage, note: str, *, actor: User
) -> PartyMessage:
    await _decide(session, message, "declined", actor, note.strip())
    record(
        session,
        actor=actor,
        action="party_sms.decline",
        subject_type="party_message",
        subject_id=message.id,
    )
    await session.commit()
    return message


async def listing(session: AsyncSession, me: uuid.UUID) -> list[dict]:
    """Every party message, newest first, with how delivery went."""
    messages = list(
        await session.scalars(select(PartyMessage).order_by(PartyMessage.created_at.desc()))
    )
    counts: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    for message_id, status, n in await session.execute(
        select(SmsLog.party_message_id, SmsLog.status, func.count())
        .where(SmsLog.party_message_id.in_([m.id for m in messages]))
        .group_by(SmsLog.party_message_id, SmsLog.status)
    ):
        counts[message_id][status] = n
    people = {m.drafted_by_id for m in messages} | {m.decided_by_id for m in messages}
    names = {
        u.id: u.full_name or u.username
        for u in await session.scalars(select(User).where(User.id.in_(people - {None})))
    }
    wards = {m.ward_id for m in messages} - {None}
    constituencies = {m.constituency_id for m in messages} - {None}
    counties = {m.county_id for m in messages} - {None}
    ward_names = dict(
        (await session.execute(select(Ward.id, Ward.name).where(Ward.id.in_(wards)))).all()
    )
    constituency_names = dict(
        (
            await session.execute(
                select(Constituency.id, Constituency.name).where(
                    Constituency.id.in_(constituencies)
                )
            )
        ).all()
    )
    county_names = dict(
        (await session.execute(select(County.id, County.name).where(County.id.in_(counties)))).all()
    )
    return [
        {
            "id": m.id,
            "body": m.body,
            "audience": m.audience,
            "place": ward_names.get(m.ward_id)
            or constituency_names.get(m.constituency_id)
            or county_names.get(m.county_id)
            or "Everywhere",
            "status": m.status,
            "drafted_by": names.get(m.drafted_by_id, ""),
            "decided_by": names.get(m.decided_by_id, ""),
            "created_at": m.created_at,
            "decided_at": m.decided_at,
            "note": m.note,
            "targeted": m.targeted,
            "recipients": m.recipients,
            "delivery": counts.get(m.id, {}),
            "mine": m.drafted_by_id == me,
        }
        for m in messages
    ]
