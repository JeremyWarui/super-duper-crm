"""Rallies and meetings: scheduling, attendance, and texting invitations."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
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
from backend.config import get_settings
from backend.models import CampaignMessage, Event, EventStatus, SmsOutbox, SmsRun, Supporter, User
from backend.schemas.campaign import (
    EventCreate,
    EventInvite,
    EventInviteResult,
    EventRead,
    EventRecord,
    EventSignups,
    EventWebsite,
    InviteRecipient,
)
from backend.services import messages, sms_queue, texting
from backend.services.errors import Forbidden
from backend.services.permissions import reach, refusal
from backend.services.sms import get_sms_provider, parts_of

router = APIRouter(prefix="/events", tags=["events"])

LOADED = (selectinload(Event.ward),)
Reader = Annotated[User, Depends(require("events.read"))]
Writer = Annotated[User, Depends(require("events.write"))]
# Putting an event on the public website is editing the website.
Publisher = Annotated[User, Depends(require("site.write"))]
PUBLISHERS = "Only the candidate, the manager or comms puts an event on the website."


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


@router.post("/{event_id}/website/", response_model=EventRead)
async def set_website(
    event_id: uuid.UUID, payload: EventWebsite, session: SessionDep, user: Publisher
) -> Event:
    """Show or hide the event on the public website, with its description and photo."""
    event = await require_visible(session, user, Event, event_id, "event", "events.read", LOADED)
    event.published = payload.published
    event.description = payload.description.strip()
    event.image_url = payload.image_url
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

    shown = payload.published or payload.description or payload.image_url
    if shown and reach(user, "site.write") is None:
        raise Forbidden(PUBLISHERS)
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
        published=payload.published,
        description=payload.description.strip(),
        image_url=payload.image_url,
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
async def delete_event(event_id: uuid.UUID, session: SessionDep, user: Writer) -> None:
    event = await require_visible(session, user, Event, event_id, "event", "events.write")
    await session.delete(event)
    await session.commit()


@router.post("/{event_id}/invite/", response_model=EventInviteResult)
async def invite_to_event(
    event_id: uuid.UUID, payload: EventInvite, session: SessionDep, user: Writer
) -> EventInviteResult:
    """Invite the event's consenting supporters through the compliance queue: the same checks,
    sending window and batches as an approved message. A dry run sends nothing, is open to
    anyone who may change the event, and gives counts without any phone number."""
    if not payload.dry_run and reach(user, "sms.send") is None:
        raise Forbidden(refusal(user, "sms.send"))
    event = await require_visible(session, user, Event, event_id, "event", "events.write", LOADED)
    audience = messages.invite_audience(
        event,
        await area_of(session, user, "events.write"),
        whole_campaign=payload.whole_campaign,
        support_levels=payload.support_levels,
    )
    await sms_queue.check_text(session, event.campaign_id, payload.message, payload.language)
    plan = await sms_queue.plan_audience(session, event.campaign_id, audience)
    text = texting.text_of(payload.message)
    unusable = [
        InviteRecipient(phone=p, status="invalid", detail="Not a usable number.")
        for p in plan.unusable
    ]
    matched = len(plan.queued) + plan.no_consent + plan.opted_out + len(plan.unusable)
    cost = len(plan.queued) * parts_of(text) * get_settings().sms_part_price_cents

    if payload.dry_run:
        return EventInviteResult(
            provider=get_sms_provider().name,
            delivered=False,
            dry_run=True,
            message=text,
            parts=parts_of(text),
            supporters_matched=matched,
            requested=len(plan.queued),
            opted_out=plan.opted_out,
            accepted=[],
            rejected=[r.model_copy(update={"phone": ""}) for r in unusable],
            detail="Nothing was sent: this was a preview.",
            number_reached=event.number_reached,
            queued=len(plan.queued),
            estimated_cost_cents=cost,
        )

    message = CampaignMessage(
        campaign_id=event.campaign_id,
        body=payload.message.strip(),
        wards=[] if payload.whole_campaign else [str(event.ward_id)],
        drafted_by_id=user.id,
        language=payload.language,
        support_levels=[str(level) for level in payload.support_levels],
    )
    session.add(message)
    await session.flush()
    run = await sms_queue.approve(
        session, message, audience, language=payload.language, actor=user, event_id=event.id
    )
    rows = (
        await session.execute(
            select(SmsOutbox.phone, SmsOutbox.status, SmsOutbox.skip_reason)
            .where(SmsOutbox.run_id == run.id, SmsOutbox.status.in_(("sent", "failed")))
            .order_by(SmsOutbox.phone)
        )
    ).all()
    await session.refresh(event)
    return EventInviteResult(
        provider=get_sms_provider().name,
        delivered=run.sent > 0,
        dry_run=False,
        message=run.text,
        parts=run.segments,
        supporters_matched=matched,
        requested=run.targeted,
        opted_out=run.excluded_opted_out,
        accepted=[InviteRecipient(phone=p, status=s) for p, s, _ in rows if s == "sent"],
        rejected=[
            *[InviteRecipient(phone=p, status=s, detail=d) for p, s, d in rows if s == "failed"],
            *unusable,
        ],
        detail=_stage_note(run),
        number_reached=event.number_reached,
        queued=run.targeted,
        run_status=run.status,
        estimated_cost_cents=run.estimated_cost_cents,
    )


def _stage_note(run: SmsRun) -> str:
    if run.status == "completed":
        return f"Sent to {run.sent} of {run.targeted}."
    if run.status == "sending":
        return f"Sending in batches: {run.sent} of {run.targeted} so far."
    if run.status == "awaiting_vetting":
        return "Waiting for the provider's vetting reference before sending."
    return "Waiting for the sending window (08:00 to 18:00) to send."
