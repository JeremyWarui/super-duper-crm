"""Online meetings on LiveKit (DM-4): starting a room, a short-lived token to join it, ending it,
and attendance from LiveKit's signed webhooks."""

from __future__ import annotations

import importlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import Meeting, MeetingAttendance, User, UserRole
from backend.services import units
from backend.services.audit import record
from backend.services.errors import Forbidden, Refused


class _LiveKit:
    """`livekit.api`, imported on first use: it is heavy and only calls need it."""

    def __getattr__(self, name: str):
        return getattr(importlib.import_module("livekit.api"), name)


api = _LiveKit()

NOT_CONFIGURED = (
    "Meetings are not configured: add LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET."
)
# Besides the host, these end a call for everyone.
ENDERS = (UserRole.CANDIDATE, UserRole.MANAGER)
TOKEN_TTL = timedelta(minutes=15)
# A room nobody joins closes itself after this long.
EMPTY_TIMEOUT_SECONDS = 10 * 60


def server_url(url: str) -> str:
    """The server API wants https:// where the browser connects with wss://."""
    return url.replace("wss://", "https://", 1).replace("ws://", "http://", 1)


class LiveKitRooms:
    """The two server calls the app makes; tests replace this."""

    async def create(self, name: str) -> None:
        s = get_settings()
        async with api.LiveKitAPI(
            server_url(s.livekit_url), s.livekit_api_key, s.livekit_api_secret
        ) as lk:
            await lk.room.create_room(
                api.CreateRoomRequest(name=name, empty_timeout=EMPTY_TIMEOUT_SECONDS)
            )

    async def close(self, name: str) -> None:
        s = get_settings()
        async with api.LiveKitAPI(
            server_url(s.livekit_url), s.livekit_api_key, s.livekit_api_secret
        ) as lk:
            await lk.room.delete_room(api.DeleteRoomRequest(room=name))


rooms = LiveKitRooms()


def require_configured() -> None:
    if not get_settings().meetings_configured:
        raise Refused(NOT_CONFIGURED)


async def start(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    title: str,
    mode: str,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None = None,
    *,
    actor: User,
) -> tuple[Meeting, list[uuid.UUID]]:
    """Open a room and record the meeting; returns it and who it rings. Commits."""
    require_configured()
    meeting = Meeting(
        campaign_id=campaign_id,
        title=title.strip(),
        mode=mode,
        host_id=actor.id,
        ward_id=ward_id,
        registration_centre_id=centre_id,
        livekit_room=f"m-{uuid.uuid4().hex}",
        started_at=datetime.now(UTC),
    )
    await rooms.create(meeting.livekit_room)
    session.add(meeting)
    await session.flush()
    record(
        session,
        actor=actor,
        action="meetings.start",
        subject_type="meeting",
        subject_id=meeting.id,
        campaign_id=campaign_id,
        detail={
            "mode": mode,
            "ward": str(ward_id) if ward_id else None,
            "centre": str(centre_id) if centre_id else None,
        },
    )
    await session.commit()
    return meeting, await units.logins(session, campaign_id, ward_id, centre_id)


def join_token(meeting: Meeting, user: User) -> str:
    """A 15-minute token for this login and this room only; an audio meeting publishes the
    microphone alone."""
    require_configured()
    if meeting.status != "live":
        raise Refused("This call has ended.")
    s = get_settings()
    sources = ["microphone"] if meeting.mode == "audio" else ["camera", "microphone"]
    grants = api.VideoGrants(
        room_join=True,
        room=meeting.livekit_room,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
        can_publish_sources=sources,
    )
    return (
        api.AccessToken(s.livekit_api_key, s.livekit_api_secret)
        .with_identity(str(user.id))
        .with_name(user.display_name)
        .with_ttl(TOKEN_TTL)
        .with_grants(grants)
        .to_jwt()
    )


async def end(session: AsyncSession, meeting: Meeting, *, actor: User) -> Meeting:
    """The host, or a lead of the campaign, ends the call for everyone. Commits."""
    if meeting.host_id != actor.id and actor.role not in ENDERS:
        raise Forbidden("Only the host, the candidate or the manager ends a call for everyone.")
    if meeting.status == "live":
        await rooms.close(meeting.livekit_room)
        _close(meeting, datetime.now(UTC))
        record(
            session,
            actor=actor,
            action="meetings.end",
            subject_type="meeting",
            subject_id=meeting.id,
            campaign_id=meeting.campaign_id,
        )
        await session.commit()
    return meeting


def _close(meeting: Meeting, at: datetime) -> None:
    meeting.status, meeting.ended_at = "ended", meeting.ended_at or at


def receive_webhook(body: str, authorization: str) -> api.WebhookEvent:
    """LiveKit's event, or Refused when the signature does not check out."""
    s = get_settings()
    if not s.meetings_configured:
        raise Refused(NOT_CONFIGURED)
    receiver = api.WebhookReceiver(api.TokenVerifier(s.livekit_api_key, s.livekit_api_secret))
    try:
        return receiver.receive(body, authorization)
    except Exception as failed:
        raise Refused("Bad webhook signature.") from failed


async def apply_event(session: AsyncSession, event: api.WebhookEvent) -> bool:
    """Record a join, a leave or the room's end; returns whether it changed anything. Commits."""
    meeting = await session.scalar(select(Meeting).where(Meeting.livekit_room == event.room.name))
    if meeting is None:
        return False
    at = datetime.fromtimestamp(event.created_at, UTC) if event.created_at else datetime.now(UTC)
    if event.event == "room_finished":
        _close(meeting, at)
    elif event.event in ("participant_joined", "participant_left"):
        try:
            user_id = uuid.UUID(event.participant.identity)
        except ValueError:
            return False
        open_stay = await session.scalar(
            select(MeetingAttendance)
            .where(
                MeetingAttendance.meeting_id == meeting.id,
                MeetingAttendance.user_id == user_id,
                MeetingAttendance.left_at.is_(None),
            )
            .order_by(MeetingAttendance.joined_at.desc())
            .limit(1)
        )
        if event.event == "participant_joined":
            if open_stay is not None:
                return False
            session.add(MeetingAttendance(meeting_id=meeting.id, user_id=user_id, joined_at=at))
        else:
            if open_stay is None:
                return False
            open_stay.left_at = at
    else:
        return False
    await session.commit()
    return True


def _aware(at: datetime) -> datetime:
    """A stored time as UTC; SQLite hands times back without their zone."""
    return at if at.tzinfo else at.replace(tzinfo=UTC)


async def calls(session: AsyncSession, campaign_id: uuid.UUID) -> list[dict]:
    """The campaign's meetings, newest first, each with who came and for how long."""
    meetings = list(
        await session.scalars(
            select(Meeting)
            .where(Meeting.campaign_id == campaign_id)
            .order_by(Meeting.started_at.desc())
            .limit(50)
        )
    )
    stays = (
        (
            await session.execute(
                select(MeetingAttendance, User)
                .outerjoin(User, User.id == MeetingAttendance.user_id)
                .where(MeetingAttendance.meeting_id.in_([m.id for m in meetings]))
                .order_by(MeetingAttendance.joined_at)
            )
        ).all()
        if meetings
        else []
    )
    hosts = (
        {
            u.id: u.display_name
            for u in await session.scalars(
                select(User).where(or_(*[User.id == m.host_id for m in meetings if m.host_id]))
            )
        }
        if any(m.host_id for m in meetings)
        else {}
    )
    places = await units.labels(session, [(m.ward_id, m.registration_centre_id) for m in meetings])
    out = []
    for m in meetings:
        people = [
            {
                "name": person.display_name if person is not None else "Former login",
                "joined_at": stay.joined_at,
                "left_at": stay.left_at,
            }
            for stay, person in stays
            if stay.meeting_id == m.id
        ]
        end_at = _aware(m.ended_at or datetime.now(UTC))
        started = _aware(m.started_at)
        out.append(
            {
                "meeting": m,
                "host": hosts.get(m.host_id, ""),
                "unit": places[(m.ward_id, m.registration_centre_id)],
                "minutes": max(int((end_at - started).total_seconds() // 60), 0),
                "attendance": people,
            }
        )
    return out
