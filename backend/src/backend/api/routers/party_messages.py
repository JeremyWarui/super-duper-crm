"""The party office's texts to members and volunteers (`services/party_messages.py`): the Comms
Officer drafts, the Party Super Admin sends or declines."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.deps import AdminUser, SessionDep, require_party_role
from backend.api.install import PartyOnlyRoute
from backend.models import PartyRoleName, User
from backend.schemas.messages import MessageDecline
from backend.schemas.party_messages import (
    Audiences,
    PartyMessageDraft,
    PartyMessageRead,
    PartyMessages,
    PartyReach,
)
from backend.services import party_messages

router = APIRouter(prefix="/party/messages", tags=["party"], route_class=PartyOnlyRoute)

CommsOfficer = Annotated[User, Depends(require_party_role(PartyRoleName.COMMS_OFFICER))]


async def _read(session, me: uuid.UUID, message_id: uuid.UUID) -> dict:
    return next(r for r in await party_messages.listing(session, me) if r["id"] == message_id)


@router.get("/", response_model=PartyMessages)
async def list_messages(session: SessionDep, user: CommsOfficer) -> dict:
    return {
        "can_send": user.is_superuser,
        "messages": await party_messages.listing(session, user.id),
    }


@router.post("/preview/", response_model=PartyReach)
async def preview(payload: Audiences, session: SessionDep, _: CommsOfficer) -> dict:
    return await party_messages.preview(session, payload.audience, payload.county, payload.ward)


@router.post("/", response_model=PartyMessageRead, status_code=status.HTTP_201_CREATED)
async def draft(payload: PartyMessageDraft, session: SessionDep, user: CommsOfficer) -> dict:
    message = await party_messages.draft(
        session,
        body=payload.body,
        audience=payload.audience,
        county_id=payload.county,
        ward_id=payload.ward,
        actor=user,
    )
    return await _read(session, user.id, message.id)


@router.post("/{message_id}/send/", response_model=PartyMessageRead)
async def send(message_id: uuid.UUID, session: SessionDep, user: AdminUser) -> dict:
    message = await party_messages.get(session, message_id)
    await party_messages.send(session, message, actor=user)
    return await _read(session, user.id, message_id)


@router.post("/{message_id}/decline/", response_model=PartyMessageRead)
async def decline(
    message_id: uuid.UUID, payload: MessageDecline, session: SessionDep, user: AdminUser
) -> dict:
    message = await party_messages.get(session, message_id)
    await party_messages.decline(session, message, payload.note, actor=user)
    return await _read(session, user.id, message_id)
