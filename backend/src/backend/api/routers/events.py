"""Rallies and meetings: scheduling, attendance, and texting invitations."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.api.deps import SessionDep, require
from backend.api.scope import (
    all_rows,
    area_of,
    load,
    own_ground_row,
    require_campaign_mobilizer,
    require_mobilizer_in_area,
    require_place,
    require_visible,
    scoped,
)
from backend.models import Event, EventStatus, Supporter, User
from backend.schemas.campaign import (
    EventCreate,
    EventInvite,
    EventInviteResult,
    EventRead,
    EventRecord,
    EventSignups,
    InviteRecipient,
)
from backend.services import texting
from backend.services.permissions import reach, refusal
from backend.services.sms import Recipient, SendResult, get_sms_provider, normalise_all

router = APIRouter(prefix="/events", tags=["events"])

LOADED = (selectinload(Event.ward),)
Reader = Annotated[User, Depends(require("events.read"))]
Writer = Annotated[User, Depends(require("events.write"))]


@router.get("/", response_model=list[EventRead])
async def list_events(
    session: SessionDep, user: Reader, campaign: uuid.UUID | None = None
) -> list[EventRead]:
    """Events newest first, each with its sign-ups; the sign-up code only for those who may
    change events."""
    statement = await scoped(
        session, user, select(Event).options(*LOADED), Event, campaign, "events.read"
    )
    events = await all_rows(session, statement.order_by(Event.scheduled_date.desc().nulls_last()))
    counts = dict(
        (
            await session.execute(
                select(Supporter.event_id, func.count())
                .where(Supporter.event_id.in_([e.id for e in events]))
                .group_by(Supporter.event_id)
            )
        ).all()
    )
    shows_code = reach(user, "events.write") is not None
    return [
        EventRead.model_validate(e).model_copy(
            update={
                "signups": counts.get(e.id, 0),
                "signup_code": e.signup_code if shows_code else None,
            }
        )
        for e in events
    ]


@router.post("/{event_id}/signups/", response_model=EventRead)
async def set_signups(
    event_id: uuid.UUID, payload: EventSignups, session: SessionDep, user: Writer
) -> Event:
    """Open or close the event's public sign-up link."""
    event = await require_visible(session, user, Event, event_id, "event", "events.write", LOADED)
    event.signups_open = payload.open
    await session.commit()
    return await load(session, Event, event.id, LOADED)


@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventCreate, session: SessionDep, user: Writer) -> Event:
    """Schedule an event; a mobilizer's own is credited to them."""
    await require_place(
        session, user, "events.write", payload.campaign, payload.ward, payload.registration_centre
    )
    await require_campaign_mobilizer(session, payload.campaign, payload.mobilizer)
    await require_mobilizer_in_area(session, user, "events.write", payload.mobilizer)

    own = own_ground_row(user, payload.campaign)
    event = Event(
        campaign_id=payload.campaign,
        ward_id=payload.ward,
        registration_centre_id=payload.registration_centre,
        mobilizer_id=payload.mobilizer or (own.id if own is not None else None),
        title=payload.title,
        venue=payload.venue,
        scheduled_date=payload.scheduled_date,
        status=payload.status,
    )
    session.add(event)
    await session.commit()
    return await load(session, Event, event.id, LOADED)


@router.post("/{event_id}/record/", response_model=EventRead)
async def record_event(
    event_id: uuid.UUID, payload: EventRecord, session: SessionDep, user: Writer
) -> Event:
    """Close an event with its attendance."""
    event = await require_visible(session, user, Event, event_id, "event", "events.write", LOADED)
    event.number_reached = payload.number_reached
    event.number_attended = payload.number_attended
    event.status = EventStatus.DONE
    await session.commit()
    return await load(session, Event, event.id, LOADED)


@router.delete("/{event_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: uuid.UUID, session: SessionDep, user: Writer) -> Response:
    event = await require_visible(session, user, Event, event_id, "event", "events.write")
    await session.delete(event)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_sent(message: str, accepted: list[Recipient], detail: str) -> SendResult:
    return SendResult(
        provider=get_sms_provider().name,
        delivered=False,
        message=message,
        requested=len(accepted),
        accepted=accepted,
        detail=detail,
    )


@router.post("/{event_id}/invite/", response_model=EventInviteResult)
async def invite_to_event(
    event_id: uuid.UUID, payload: EventInvite, session: SessionDep, user: Writer
) -> EventInviteResult:
    """Text the event's consenting supporters and set `number_reached`; a dry run sends nothing
    and is open to anyone who may change the event."""
    if not payload.dry_run and reach(user, "sms.send") is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refusal(user, "sms.send"))
    event = await require_visible(session, user, Event, event_id, "event", "events.write", LOADED)

    statement = select(Supporter).where(
        Supporter.campaign_id == event.campaign_id, Supporter.consent_given.is_(True)
    )
    if not payload.whole_campaign:
        statement = statement.where(Supporter.ward_id == event.ward_id)
    if payload.support_levels:
        statement = statement.where(Supporter.support_level.in_(payload.support_levels))
    area = await area_of(session, user, "events.write")
    if area is not None:
        statement = statement.where(area.where(Supporter.ward_id, Supporter.registration_centre_id))

    supporters = await all_rows(session, statement)
    numbers, unusable = normalise_all([s.phone for s in supporters])
    text = payload.message.strip() + texting.FOOTER

    if payload.dry_run:
        blocked = await texting.opted_out(session, event.campaign_id, numbers)
        would = [Recipient(phone=n, status="would send") for n in numbers if n not in blocked]
        result = _not_sent(text, would, "Nothing was sent: this was a dry run.")
        left_out = len(blocked)
    elif not numbers:
        result = _not_sent(text, [], "Nobody on this register has a usable phone number.")
        left_out = 0
    else:
        result, left_out = await texting.send(
            session,
            numbers,
            text,
            purpose="invite",
            sender=user,
            campaign_id=event.campaign_id,
            event_id=event.id,
        )
        if result.delivered:
            event.number_reached = len(result.accepted)
        await session.commit()

    def shown(r: Recipient) -> InviteRecipient:
        return InviteRecipient(phone=r.phone, status=r.status, detail=r.detail)

    return EventInviteResult(
        provider=result.provider,
        delivered=result.delivered,
        dry_run=payload.dry_run,
        message=result.message,
        parts=result.parts,
        supporters_matched=len(supporters),
        requested=result.requested,
        opted_out=left_out,
        accepted=[shown(r) for r in result.accepted],
        rejected=[shown(r) for r in [*result.rejected, *unusable]],
        detail=result.detail,
        number_reached=event.number_reached,
    )
