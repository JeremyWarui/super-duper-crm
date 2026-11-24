"""Announcements from the campaign's leads to the whole campaign, a ward or a centre
(`services/announcements.py`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.deps import CurrentUser, SessionDep, require
from backend.api.scope import area_of, require_visible_campaign, require_ward_in_campaign
from backend.models import User
from backend.schemas.announcements import AnnouncementRead, AnnouncementSend, AnnouncementSent
from backend.services import announcements, push, units
from backend.services.errors import Refused
from backend.services.permissions import reach

router = APIRouter(tags=["announcements"])

Sender = Annotated[User, Depends(require("announcements.send"))]
OUTSIDE = "Pick a ward or centre in your area to announce to."


@router.post(
    "/campaigns/{campaign_id}/announcements/",
    response_model=AnnouncementSent,
    status_code=status.HTTP_201_CREATED,
)
async def send(
    campaign_id: uuid.UUID, payload: AnnouncementSend, session: SessionDep, user: Sender
) -> AnnouncementSent:
    """Announce to a unit's team: a notice under each bell and an alert on their devices."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    ward, centre = await units.resolve(session, payload.ward, payload.centre)
    await require_ward_in_campaign(session, campaign, ward, centre)
    area = await area_of(session, user, "announcements.send")
    if area is not None and (ward is None or not area.holds(ward, centre)):
        raise Refused(OUTSIDE)
    announcement, recipients = await announcements.send(
        session, campaign_id, payload.title, payload.body, ward, centre, actor=user
    )
    alerted = await push.notify(
        session,
        recipients,
        f"Announcement: {announcement.title}",
        announcement.body[:120],
        announcements.PAGE,
    )
    listed = await announcements.listing(session, campaign_id, user, area, sender=True)
    sent = next(a for a in listed if a["id"] == announcement.id)
    return AnnouncementSent(announcement=AnnouncementRead.model_validate(sent), alerted=alerted)


@router.get("/campaigns/{campaign_id}/announcements/", response_model=list[AnnouncementRead])
async def listing(campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> list:
    """What the caller was sent and, for those who announce, what went out within their reach
    with how many have read it."""
    await require_visible_campaign(session, user, campaign_id)
    sender = reach(user, "announcements.send") is not None
    area = await area_of(session, user, "announcements.send") if sender else None
    return await announcements.listing(session, campaign_id, user, area, sender=sender)


@router.post("/campaigns/{campaign_id}/announcements/read/", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    """The caller has opened their announcements."""
    await require_visible_campaign(session, user, campaign_id)
    await announcements.mark_read(session, campaign_id, user)
