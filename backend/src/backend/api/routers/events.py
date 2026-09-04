"""Rallies and meetings, and the attendance recorded after they happen.

Mobilizers write here: scheduling and recording in their own ward is their job.
"""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import CurrentUser, MobilizerWriter, SessionDep, mobilizer_ward_id
from backend.api.scope import (
    limit_to_campaigns,
    mobilizer_profile_for,
    require_own_ward,
    require_visible_campaign,
    visible_campaign_ids,
)
from backend.models import Event, EventStatus, User
from backend.schemas.campaign import EventCreate, EventRead, EventRecord

router = APIRouter(prefix="/events", tags=["events"])

LOADED = (selectinload(Event.ward),)


@router.get("/", response_model=list[EventRead])
async def list_events(
    session: SessionDep, user: CurrentUser, campaign: uuid.UUID | None = None
) -> list[Event]:
    statement = select(Event).options(*LOADED)
    if campaign is not None:
        statement = statement.where(Event.campaign_id == campaign)
    statement = limit_to_campaigns(
        statement, Event.campaign_id, await visible_campaign_ids(session, user)
    )
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(Event.ward_id == own_ward)
    statement = statement.order_by(Event.scheduled_date.desc().nulls_last())
    return list((await session.execute(statement)).scalars().all())


@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    session: SessionDep,
    user: CurrentUser,
    _: MobilizerWriter,
) -> Event:
    await require_visible_campaign(session, user, payload.campaign)
    require_own_ward(user, payload.ward)

    profile = await mobilizer_profile_for(session, user)
    event = Event(
        campaign_id=payload.campaign,
        ward_id=payload.ward,
        registration_centre_id=payload.registration_centre,
        # A mobilizer's own event is credited to them without being asked for.
        mobilizer_id=payload.mobilizer or (profile.id if profile is not None else None),
        title=payload.title,
        venue=payload.venue,
        scheduled_date=payload.scheduled_date,
        status=payload.status,
    )
    session.add(event)
    await session.commit()
    return await _reload(session, event.id)


@router.post("/{event_id}/record/", response_model=EventRead)
async def record_event(
    event_id: uuid.UUID,
    payload: EventRecord,
    session: SessionDep,
    user: CurrentUser,
    _: MobilizerWriter,
) -> Event:
    """Close an event: how many were reached, how many came, and mark it done."""
    event = await _visible_event(session, user, event_id)
    event.number_reached = payload.number_reached
    event.number_attended = payload.number_attended
    event.status = EventStatus.DONE
    await session.commit()
    return await _reload(session, event.id)


@router.delete("/{event_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    _: MobilizerWriter,
) -> Response:
    event = await _visible_event(session, user, event_id)
    await session.delete(event)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _visible_event(session: SessionDep, user: User, event_id: uuid.UUID) -> Event:
    event = (
        await session.execute(select(Event).where(Event.id == event_id).options(*LOADED))
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such event.")
    await require_visible_campaign(session, user, event.campaign_id)
    require_own_ward(user, event.ward_id)
    return event


async def _reload(session: SessionDep, event_id: uuid.UUID) -> Event:
    return (
        await session.execute(select(Event).where(Event.id == event_id).options(*LOADED))
    ).scalar_one()
