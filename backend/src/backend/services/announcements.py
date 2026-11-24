"""Send an announcement to a unit's team as notices under the bell, and list announcements
with their read receipts."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Announcement, Notice, User
from backend.services import units
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.notices import preview
from backend.services.permissions import Area

PAGE = "/campaign/announcements"
NOBODY = "Nobody in that place has a login yet, so there is no one to announce to."


async def send(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    title: str,
    body: str,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None,
    *,
    actor: User,
) -> tuple[Announcement, list[uuid.UUID]]:
    """Record the announcement and give each of the unit's logins, but its author, a notice;
    returns it and who it went to. Commits."""
    found = await units.logins(session, campaign_id, ward_id, centre_id)
    recipients = [user_id for user_id in found if user_id != actor.id]
    if not recipients:
        raise Refused(NOBODY)
    announcement = Announcement(
        campaign_id=campaign_id,
        author_id=actor.id,
        title=title.strip(),
        body=body.strip(),
        ward_id=ward_id,
        registration_centre_id=centre_id,
    )
    session.add(announcement)
    await session.flush()
    session.add_all(
        Notice(
            campaign_id=campaign_id,
            user_id=user_id,
            text=f"Announcement: {announcement.title}",
            url=PAGE,
            announcement_id=announcement.id,
            sender_id=actor.id,
            detail=preview(announcement.body),
        )
        for user_id in recipients
    )
    record(
        session,
        actor=actor,
        action="announcements.send",
        subject_type="announcement",
        subject_id=announcement.id,
        campaign_id=campaign_id,
        detail={
            "ward": str(ward_id) if ward_id else None,
            "centre": str(centre_id) if centre_id else None,
            "recipients": len(recipients),
        },
    )
    await session.commit()
    return announcement, recipients


async def listing(
    session: AsyncSession, campaign_id: uuid.UUID, user: User, reach: Area | None, sender: bool
) -> list[dict]:
    """The newest 50 announcements the caller received or, when they may announce (`sender`),
    sent within their reach (`reach` None for everywhere). Senders see read receipts."""
    received = select(Notice.announcement_id).where(
        Notice.user_id == user.id, Notice.announcement_id.is_not(None)
    )
    shown = Announcement.id.in_(received)
    if sender and reach is None:
        shown = or_(shown, Announcement.campaign_id == campaign_id)
    elif sender:
        shown = or_(
            shown,
            Announcement.author_id == user.id,
            reach.where(Announcement.ward_id, Announcement.registration_centre_id),
        )
    rows = list(
        await session.scalars(
            select(Announcement)
            .where(Announcement.campaign_id == campaign_id, shown)
            .order_by(Announcement.created_at.desc())
            .limit(50)
        )
    )
    if not rows:
        return []
    ids = [a.id for a in rows]
    places = await units.labels(session, [(a.ward_id, a.registration_centre_id) for a in rows])
    author_ids = {a.author_id for a in rows if a.author_id}
    authors = {
        u.id: u.display_name
        for u in await session.scalars(select(User).where(User.id.in_(author_ids)))
    }
    counts = {
        announcement_id: (total, read)
        for announcement_id, total, read in (
            await session.execute(
                select(Notice.announcement_id, func.count(), func.count(Notice.read_at))
                .where(Notice.announcement_id.in_(ids))
                .group_by(Notice.announcement_id)
            )
        ).all()
    }
    own = dict(
        (
            await session.execute(
                select(Notice.announcement_id, Notice.read_at).where(
                    Notice.announcement_id.in_(ids), Notice.user_id == user.id
                )
            )
        ).all()
    )
    out = []
    for a in rows:
        total, read = counts.get(a.id, (0, 0))
        # Whoever may announce to this place sees its receipts; a plain recipient does not.
        receipts = sender and (
            reach is None
            or a.author_id == user.id
            or (a.ward_id is not None and reach.holds(a.ward_id, a.registration_centre_id))
        )
        out.append(
            {
                "id": a.id,
                "title": a.title,
                "body": a.body,
                "unit": places[(a.ward_id, a.registration_centre_id)],
                "author": authors.get(a.author_id, "Former login"),
                "created_at": a.created_at,
                "recipients": total if receipts else None,
                "read": read if receipts else None,
                "read_by_me": (own[a.id] is not None) if a.id in own else None,
            }
        )
    return out


async def mark_read(session: AsyncSession, campaign_id: uuid.UUID, user: User) -> None:
    """The caller has seen every announcement sent to them in this campaign. Commits."""
    await session.execute(
        update(Notice)
        .where(
            Notice.campaign_id == campaign_id,
            Notice.user_id == user.id,
            Notice.announcement_id.is_not(None),
            Notice.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()
