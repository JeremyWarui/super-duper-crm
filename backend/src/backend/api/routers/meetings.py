"""Online calls for the campaign's logins (`services/meetings.py`), LiveKit's webhook, and the
call alerts each device signs up for (`services/push.py`). A started call also leaves a notice
under each invitee's bell (`services/notices.py`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from backend.api.deps import CurrentUser, SessionDep, require
from backend.api.scope import area_of, require_visible_campaign, require_ward_in_campaign
from backend.config import get_settings
from backend.models import Meeting, User
from backend.schemas.meetings import (
    CallRead,
    MeetingJoin,
    MeetingRead,
    MeetingStart,
    MeetingStarted,
    PushKey,
    PushSubscribe,
    PushUnsubscribe,
)
from backend.services import meetings, notices, push, units
from backend.services.errors import NotFound, Refused

router = APIRouter(tags=["meetings"])

Starter = Annotated[User, Depends(require("meetings.start"))]
Joiner = Annotated[User, Depends(require("meetings.join"))]
WARD_REQUIRED = "Pick a ward or centre in your area to call."


async def _meeting(session, user: User, meeting_id: uuid.UUID) -> Meeting:
    meeting = await session.get(Meeting, meeting_id)
    if meeting is None:
        raise NotFound("No such call.")
    await require_visible_campaign(session, user, meeting.campaign_id)
    return meeting


@router.post(
    "/campaigns/{campaign_id}/meetings/",
    response_model=MeetingStarted,
    status_code=status.HTTP_201_CREATED,
)
async def start(
    campaign_id: uuid.UUID, payload: MeetingStart, session: SessionDep, user: Starter
) -> MeetingStarted:
    """Open a call, leave each invitee a notice and ring their devices."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    ward, centre = await units.resolve(session, payload.ward, payload.centre)
    await require_ward_in_campaign(session, campaign, ward, centre)
    area = await area_of(session, user, "meetings.start")
    if area is not None and (ward is None or not area.holds(ward, centre)):
        raise Refused(WARD_REQUIRED)
    meeting, invited = await meetings.start(
        session, campaign_id, payload.title, payload.mode, ward, centre, actor=user
    )
    path = f"/meet/{meeting.id}"
    alerted = await notices.tell(
        session,
        campaign_id,
        invited,
        f"Call started: {meeting.title}",
        path,
        detail="Tap to join.",
        sender_id=user.id,
        title=f"Joining: {meeting.title}",
    )
    return MeetingStarted(
        meeting=MeetingRead.model_validate(meeting), join_path=path, alerted=alerted
    )


@router.get("/campaigns/{campaign_id}/meetings/", response_model=list[CallRead])
async def calls(campaign_id: uuid.UUID, session: SessionDep, user: Starter) -> list:
    """Past and live calls with who came and for how long."""
    await require_visible_campaign(session, user, campaign_id)
    return await meetings.calls(session, campaign_id)


@router.get("/campaigns/{campaign_id}/meetings/live/", response_model=list[MeetingRead])
async def live(campaign_id: uuid.UUID, session: SessionDep, user: Joiner) -> list[Meeting]:
    """The live calls the caller is invited to."""
    await require_visible_campaign(session, user, campaign_id)
    return await meetings.live_for(session, campaign_id, user)


@router.get("/meetings/{meeting_id}/token/", response_model=MeetingJoin)
async def token(meeting_id: uuid.UUID, session: SessionDep, user: Joiner) -> MeetingJoin:
    """A 15-minute LiveKit token for this call and this login."""
    meeting = await _meeting(session, user, meeting_id)
    return MeetingJoin(
        meeting=MeetingRead.model_validate(meeting),
        token=meetings.join_token(meeting, user),
        url=get_settings().livekit_url,
        can_end=meeting.host_id == user.id or user.role in meetings.ENDERS,
    )


@router.post("/meetings/{meeting_id}/end/", response_model=MeetingRead)
async def end(meeting_id: uuid.UUID, session: SessionDep, user: Joiner) -> Meeting:
    """End the call for everyone."""
    meeting = await _meeting(session, user, meeting_id)
    return await meetings.end(session, meeting, actor=user)


@router.post("/livekit/webhook/")
async def livekit_webhook(
    request: Request, session: SessionDep, authorization: Annotated[str, Header()] = ""
) -> dict[str, bool]:
    """Joins, leaves and room ends, signed by LiveKit; a bad signature gets 401."""
    body = (await request.body()).decode(errors="replace")
    try:
        event = meetings.receive_webhook(body, authorization)
    except Refused as failed:
        raise HTTPException(status_code=401, detail=str(failed)) from failed
    return {"applied": await meetings.apply_event(session, event)}


@router.get("/push/key/", response_model=PushKey)
async def push_key() -> PushKey:
    """The public key a device subscribes with; blank when call alerts are off."""
    return PushKey(key=get_settings().vapid_public_key)


@router.post("/push/subscribe/", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(payload: PushSubscribe, session: SessionDep, user: CurrentUser) -> None:
    await push.subscribe(session, user, payload.endpoint, payload.keys.p256dh, payload.keys.auth)


@router.delete("/push/subscribe/", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(payload: PushUnsubscribe, session: SessionDep, user: CurrentUser) -> None:
    await push.unsubscribe(session, user, payload.endpoint)
