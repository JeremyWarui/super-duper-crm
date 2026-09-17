"""Rallies and meetings: scheduling, attendance, and texting invitations."""

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, MobilizerWriter, SessionDep
from backend.api.scope import (
    all_rows,
    load,
    mobilizer_ward_id,
    own_ground_row,
    require_campaign_mobilizer,
    require_own_ward,
    require_visible,
    require_visible_campaign,
    require_ward_in_campaign,
    scoped,
)
from backend.models import Event, EventStatus, Supporter
from backend.schemas.campaign import (
    EventCreate,
    EventInvite,
    EventInviteResult,
    EventRead,
    EventRecord,
    InviteRecipient,
)
from backend.services.sms import Recipient, SendResult, get_sms_provider, normalise_all

router = APIRouter(prefix="/events", tags=["events"])

LOADED = (selectinload(Event.ward),)


@router.get("/", response_model=list[EventRead])
async def list_events(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> list[Event]:
    statement = await scoped(session, user, select(Event).options(*LOADED), Event, campaign)
    return await all_rows(session, statement.order_by(Event.scheduled_date.desc().nulls_last()))


@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventCreate, session: SessionDep, user: MobilizerWriter) -> Event:
    """Schedule an event; a mobilizer's own is credited to them."""
    campaign = await require_visible_campaign(session, user, payload.campaign)
    require_own_ward(user, payload.ward)
    await require_ward_in_campaign(session, campaign, payload.ward, payload.registration_centre)
    await require_campaign_mobilizer(session, payload.campaign, payload.mobilizer)

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
    event_id: uuid.UUID, payload: EventRecord, session: SessionDep, user: MobilizerWriter
) -> Event:
    """Close an event with its attendance."""
    event = await require_visible(session, user, Event, event_id, "event", LOADED)
    event.number_reached = payload.number_reached
    event.number_attended = payload.number_attended
    event.status = EventStatus.DONE
    await session.commit()
    return await load(session, Event, event.id, LOADED)


@router.delete("/{event_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: uuid.UUID, session: SessionDep, user: MobilizerWriter) -> Response:
    event = await require_visible(session, user, Event, event_id, "event")
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
    event_id: uuid.UUID, payload: EventInvite, session: SessionDep, user: MobilizerWriter
) -> EventInviteResult:
    """Text the event's supporters and set `number_reached`; a dry run sends nothing."""
    event = await require_visible(session, user, Event, event_id, "event", LOADED)

    statement = select(Supporter).where(Supporter.campaign_id == event.campaign_id)
    if not payload.whole_campaign:
        statement = statement.where(Supporter.ward_id == event.ward_id)
    if payload.support_levels:
        statement = statement.where(Supporter.support_level.in_(payload.support_levels))
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(Supporter.ward_id == own_ward)

    supporters = await all_rows(session, statement)
    numbers, unusable = normalise_all([s.phone for s in supporters])

    if payload.dry_run:
        would = [Recipient(phone=n, status="would send") for n in numbers]
        result = _not_sent(payload.message, would, "Nothing was sent: this was a dry run.")
    elif not numbers:
        result = _not_sent(
            payload.message, [], "Nobody on this register has a usable phone number."
        )
    else:
        result = await get_sms_provider().send(numbers, payload.message)

    if result.delivered and not payload.dry_run:
        event.number_reached = len(result.accepted)
        await session.commit()

    return EventInviteResult(
        provider=result.provider,
        delivered=result.delivered,
        dry_run=payload.dry_run,
        message=result.message,
        parts=result.parts,
        supporters_matched=len(supporters),
        requested=result.requested,
        accepted=[InviteRecipient(**vars(r)) for r in result.accepted],
        rejected=[InviteRecipient(**vars(r)) for r in [*result.rejected, *unusable]],
        detail=result.detail,
        number_reached=event.number_reached,
    )
