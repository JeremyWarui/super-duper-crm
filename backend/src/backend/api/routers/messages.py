"""The workspace's texts to supporters: drafted by Comms, Coordinators and the leads, sent or
declined by the Candidate or Manager (`services/messages.py`)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.deps import SessionDep, require
from backend.api.scope import area_of, require_visible_campaign
from backend.config import get_settings
from backend.models import CampaignMessage, User
from backend.schemas.messages import (
    LogRow,
    MessageDecline,
    MessageDraft,
    MessageRead,
    MessagesPage,
    Reach,
)
from backend.services import messages
from backend.services.errors import Forbidden, NotFound, Refused
from backend.services.permissions import Reach as Extent
from backend.services.permissions import reach, refusal
from backend.services.sms import get_sms_provider

router = APIRouter(prefix="/messages", tags=["messages"])

Drafter = Annotated[User, Depends(require("sms.draft"))]
Sender = Annotated[User, Depends(require("sms.send"))]


def _own_only(user: User) -> uuid.UUID | None:
    """Whose messages the caller sees: everyone's, or only their own for an area role."""
    return None if reach(user, "sms.draft") is Extent.ALL else user.id


async def _visible(session, user: User, message_id: uuid.UUID) -> CampaignMessage:
    message = await messages.get(session, message_id)
    await require_visible_campaign(session, user, message.campaign_id)
    mine = _own_only(user)
    if mine is not None and message.drafted_by_id != mine:
        raise NotFound("No such message.")
    return message


async def _read(session, user: User, message: CampaignMessage) -> dict:
    (row,) = await messages.listing(session, message.campaign_id, None, user.id, [message.id])
    return row


async def _drafter_area(session, message: CampaignMessage):
    """The area the message's drafter reaches now; a drafter who can no longer draft sends to
    nobody."""
    drafter = await session.get(User, message.drafted_by_id) if message.drafted_by_id else None
    if drafter is None or reach(drafter, "sms.draft") is None:
        raise Refused("Whoever drafted this can no longer write messages; draft it again.")
    return await area_of(session, drafter, "sms.draft")


@router.get("/", response_model=MessagesPage)
async def list_messages(campaign: uuid.UUID, session: SessionDep, user: Drafter) -> dict:
    await require_visible_campaign(session, user, campaign)
    area = await area_of(session, user, "sms.draft")
    settings = get_settings()
    return {
        "sender_id": settings.at_sender_id,
        "provider": get_sms_provider().name,
        "can_send": reach(user, "sms.send") is not None,
        "wards": await messages.addressable_wards(session, campaign, area),
        "messages": await messages.listing(session, campaign, _own_only(user), user.id),
    }


@router.post("/preview/", response_model=Reach)
async def preview(payload: MessageDraft, session: SessionDep, user: Drafter) -> dict:
    """How many supporters the message would reach now, and the text they get."""
    await require_visible_campaign(session, user, payload.campaign)
    area = await area_of(session, user, "sms.draft")
    return await messages.reach(session, payload.campaign, area, payload.wards, payload.body)


@router.post("/", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create(payload: MessageDraft, session: SessionDep, user: Drafter) -> dict:
    """Save a draft; with `send`, the Candidate or Manager sends it at once."""
    if payload.send and reach(user, "sms.send") is None:
        raise Forbidden(refusal(user, "sms.send"))
    await require_visible_campaign(session, user, payload.campaign)
    area = await area_of(session, user, "sms.draft")
    message = await messages.draft(
        session, payload.campaign, payload.body, payload.wards, area, actor=user
    )
    if payload.send:
        message = await messages.send(session, message, area, actor=user)
    return await _read(session, user, message)


@router.post("/{message_id}/send/", response_model=MessageRead)
async def send(message_id: uuid.UUID, session: SessionDep, user: Sender) -> dict:
    """Approve a draft and text it."""
    message = await _visible(session, user, message_id)
    area = await _drafter_area(session, message)
    message = await messages.send(session, message, area, actor=user)
    return await _read(session, user, message)


@router.post("/{message_id}/decline/", response_model=MessageRead)
async def decline(
    message_id: uuid.UUID, payload: MessageDecline, session: SessionDep, user: Sender
) -> dict:
    message = await _visible(session, user, message_id)
    message = await messages.decline(session, message, payload.note, actor=user)
    return await _read(session, user, message)


@router.delete("/{message_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete(message_id: uuid.UUID, session: SessionDep, user: Drafter) -> None:
    """Delete a draft: its drafter, or whoever may send."""
    message = await _visible(session, user, message_id)
    if message.drafted_by_id != user.id and reach(user, "sms.send") is None:
        raise Forbidden("Only its drafter or a sender may delete it.")
    await messages.discard(session, message)


@router.get("/{message_id}/log/", response_model=list[LogRow])
async def delivery_log(message_id: uuid.UUID, session: SessionDep, user: Sender) -> list:
    """Each number the message went to and what the gateway reported."""
    message = await _visible(session, user, message_id)
    return await messages.log(session, message)
