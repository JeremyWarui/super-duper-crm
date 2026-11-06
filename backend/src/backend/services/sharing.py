"""Counts a hosted campaign chooses to share with the party, and the party's feed to it.

The party never reads a campaign's supporters, except counts the campaign has chosen to share.
Every count is worked out when it is read, so switching a share off hides it on the next read.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AuditEvent,
    Campaign,
    CampaignSharing,
    Constituency,
    Event,
    EventStatus,
    Mobilizer,
    OfficeLevel,
    PartyMember,
    PartyMemberStatus,
    PartyPost,
    PostKind,
    PostLabel,
    Supporter,
    User,
    Ward,
    WorkspaceKind,
)
from backend.services.audit import record
from backend.services.targets import wards_in_area

SWITCHES = ("event_reach", "ward_coverage", "supporter_counts")
FEED_EVENTS = 10
FEED_NOTICES = 5


async def switches(session: AsyncSession, campaign_id: uuid.UUID) -> dict:
    """The campaign's three switches, all off when it never changed one."""
    row = await session.get(CampaignSharing, campaign_id)
    return {name: bool(row and getattr(row, name)) for name in SWITCHES}


async def change(
    session: AsyncSession, campaign: Campaign, wanted: dict[str, bool], *, actor: User
) -> dict:
    """Set the switches; each one that moves is audited."""
    row = await session.get(CampaignSharing, campaign.id, with_for_update=True)
    if row is None:
        row = CampaignSharing(campaign_id=campaign.id, **dict.fromkeys(SWITCHES, False))
        session.add(row)
    moved = {name: on for name, on in wanted.items() if getattr(row, name) != on}
    for name, on in moved.items():
        setattr(row, name, on)
        record(
            session,
            actor=actor,
            action="sharing.change",
            subject_type="campaign",
            subject_id=campaign.id,
            campaign_id=campaign.id,
            detail={"switch": name, "on": on},
        )
    if moved or row.changed_at is None:
        row.changed_by_id, row.changed_at = actor.id, datetime.now(UTC)
    await session.commit()
    return await switches(session, campaign.id)


async def history(session: AsyncSession, campaign_id: uuid.UUID, limit: int = 20) -> list[dict]:
    rows = await session.scalars(
        select(AuditEvent)
        .where(AuditEvent.campaign_id == campaign_id, AuditEvent.action == "sharing.change")
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "at": r.created_at,
            "by": r.actor_name,
            "switch": r.detail["switch"],
            "on": r.detail["on"],
        }
        for r in rows
    ]


async def _county_of(session: AsyncSession, campaign: Campaign) -> uuid.UUID | None:
    if campaign.office_level is OfficeLevel.COUNTY:
        return campaign.county_id
    constituency = campaign.constituency_id
    if campaign.office_level is OfficeLevel.WARD and campaign.ward_id is not None:
        constituency = await session.scalar(
            select(Ward.constituency_id).where(Ward.id == campaign.ward_id)
        )
    if constituency is None:
        return None
    return await session.scalar(
        select(Constituency.county_id).where(Constituency.id == constituency)
    )


def _post(p: PartyPost) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "body": p.body,
        "event_date": p.event_date,
        "venue": p.venue,
        "published_on": p.published_on,
    }


async def feed(session: AsyncSession, campaign: Campaign, today: date) -> dict:
    """What the party shows a hosted campaign: its events and notices for the campaign's county
    or the whole country, and its approved members counted per ward of the seat."""
    county = await _county_of(session, campaign)
    here = or_(PartyPost.county_id.is_(None), PartyPost.county_id == county)
    events = await session.scalars(
        select(PartyPost)
        .where(
            PartyPost.published.is_(True),
            PartyPost.kind == PostKind.EVENT,
            PartyPost.event_date >= today,
            here,
        )
        .order_by(PartyPost.event_date, PartyPost.title)
        .limit(FEED_EVENTS)
    )
    notices = await session.scalars(
        select(PartyPost)
        .where(
            PartyPost.published.is_(True),
            PartyPost.kind == PostKind.NEWS,
            PartyPost.label == PostLabel.STATEMENT,
            here,
        )
        .order_by(PartyPost.published_on.desc(), PartyPost.title)
        .limit(FEED_NOTICES)
    )
    wards = await wards_in_area(session, campaign)
    counted = dict(
        (
            await session.execute(
                select(PartyMember.ward_id, func.count())
                .where(
                    PartyMember.status == PartyMemberStatus.APPROVED,
                    PartyMember.ward_id.in_([w.id for w in wards]),
                )
                .group_by(PartyMember.ward_id)
            )
        ).all()
    )
    return {
        "events": [_post(p) for p in events],
        "notices": [_post(p) for p in notices],
        "members_by_ward": [
            {"ward_id": w.id, "ward": w.name, "count": counted.get(w.id, 0)} for w in wards
        ],
    }


async def _by_ward(session: AsyncSession, model, ids: list[uuid.UUID]) -> dict:
    """Rows of `model` counted per campaign and ward, with the ward's name."""
    rows = await session.execute(
        select(model.campaign_id, Ward.id, Ward.name, func.count())
        .join(Ward, Ward.id == model.ward_id)
        .where(model.campaign_id.in_(ids))
        .group_by(model.campaign_id, Ward.id, Ward.name)
        .order_by(Ward.name)
    )
    out = defaultdict(list)
    for campaign_id, ward_id, name, n in rows.all():
        out[campaign_id].append({"ward_id": ward_id, "ward": name, "count": n})
    return out


async def shared(session: AsyncSession) -> list[dict]:
    """Every hosted campaign with what it shares; a share that is off is None."""
    campaigns = list(
        (
            await session.scalars(
                select(Campaign)
                .where(Campaign.kind == WorkspaceKind.HOSTED)
                .order_by(Campaign.title)
            )
        ).all()
    )
    rows = {
        r.campaign_id: r
        for r in await session.scalars(
            select(CampaignSharing).where(
                CampaignSharing.campaign_id.in_([c.id for c in campaigns])
            )
        )
    }

    def on(name: str) -> list[uuid.UUID]:
        return [c for c, r in rows.items() if getattr(r, name)]

    reach = {
        campaign_id: {"events": n, "reached": reached or 0, "attended": attended or 0}
        for campaign_id, n, reached, attended in (
            await session.execute(
                select(
                    Event.campaign_id,
                    func.count(),
                    func.sum(Event.number_reached),
                    func.sum(Event.number_attended),
                )
                .where(
                    Event.campaign_id.in_(on("event_reach")),
                    Event.status == EventStatus.DONE,
                )
                .group_by(Event.campaign_id)
            )
        ).all()
    }
    mobilizers = await _by_ward(session, Mobilizer, on("ward_coverage"))
    supporters = await _by_ward(session, Supporter, on("supporter_counts"))

    out = []
    for c in campaigns:
        row = rows.get(c.id)
        coverage = None
        if row is not None and row.ward_coverage:
            covered = mobilizers.get(c.id, [])
            coverage = {"wards": len(await wards_in_area(session, c)), "covered": covered}
        out.append(
            {
                "id": c.id,
                "title": c.title,
                "seat": c.seat,
                "event_reach": (
                    reach.get(c.id, {"events": 0, "reached": 0, "attended": 0})
                    if row is not None and row.event_reach
                    else None
                ),
                "ward_coverage": coverage,
                "supporter_counts": (
                    supporters.get(c.id, []) if row is not None and row.supporter_counts else None
                ),
            }
        )
    return out
