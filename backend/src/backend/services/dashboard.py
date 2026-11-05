"""Party-wide counts for the superuser's dashboard.

A place filter keeps members and volunteers living in it, and campaigns, aspirants and
events whose own area lies inside it. `seat` and `aspirant` act through the campaign.
Campaign counts are hosted workspaces; the party's own workspace is counted apart. Only
counts, county names and recruiting coordinators' names leave; no campaign record's text does.
"""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.models import (
    Aspirant,
    AspirantStatus,
    Campaign,
    CampaignMember,
    Constituency,
    County,
    Event,
    EventStatus,
    Mobilizer,
    PartyMember,
    PartyMemberStatus,
    Seat,
    Supporter,
    User,
    VolunteerArea,
    VolunteerProfile,
    VolunteerStatus,
    Ward,
    WorkspaceKind,
)
from backend.schemas.dashboard import (
    CoordinatorCount,
    CountyCount,
    CountySeatCount,
    Dashboard,
    InterestCount,
    PartyWorkspaceTotals,
    SeatCount,
)
from backend.services import access

EVENT_DAYS = 30


@dataclass(frozen=True)
class Filters:
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    seat: Seat | None = None
    aspirant: uuid.UUID | None = None
    start: date | None = None
    end: date | None = None


def _place(county, constituency, ward, f: Filters) -> list[ColumnElement[bool]]:
    """Conditions keeping rows whose area, given as its three ids, lies inside the filter."""
    conditions = []
    if f.county:
        conditions.append(county == f.county)
    if f.constituency:
        conditions.append(constituency == f.constituency)
    if f.ward:
        conditions.append(ward == f.ward)
    return conditions


def _in_ward(query: Select, ward_column, f: Filters) -> tuple[Select, ColumnElement]:
    """Join a ward id to its county, apply the place filter; returns the query and county id."""
    ward, constituency = aliased(Ward), aliased(Constituency)
    query = query.join(ward, ward.id == ward_column).join(
        constituency, constituency.id == ward.constituency_id
    )
    query = query.where(*_place(constituency.county_id, ward.constituency_id, ward.id, f))
    return query, constituency.county_id


def _in_area(model, query: Select, f: Filters) -> tuple[Select, ColumnElement]:
    """Apply the place filter to a campaign's or aspirant's area; returns the query and county id.

    The area is one of a ward, a constituency or a county, by the seat's level.
    """
    ward, constituency = aliased(Ward), aliased(Constituency)
    constituency_id = func.coalesce(model.constituency_id, ward.constituency_id)
    county_id = func.coalesce(model.county_id, constituency.county_id)
    query = query.outerjoin(ward, ward.id == model.ward_id).outerjoin(
        constituency, constituency.id == constituency_id
    )
    return query.where(*_place(county_id, constituency_id, model.ward_id, f)), county_id


def _campaigns(f: Filters, *columns) -> tuple[Select, ColumnElement]:
    """The hosted campaigns the filters keep; returns the query and the campaign's county id."""
    query, county = _in_area(Campaign, select(*columns).select_from(Campaign), f)
    query = query.where(Campaign.kind != WorkspaceKind.PARTY)
    if f.seat:
        query = query.where(Campaign.seat == f.seat)
    if f.aspirant:
        query = query.join(Aspirant, Aspirant.campaign_id == Campaign.id).where(
            Aspirant.id == f.aspirant
        )
    return query, county


async def _count(session: AsyncSession, query: Select) -> int:
    return await session.scalar(select(func.count()).select_from(query.subquery()))


def _by_county(counts: Counter, names: dict[uuid.UUID, str]) -> list[CountyCount]:
    return [
        CountyCount(county_id=c, county=names[c], count=n)
        for c, n in sorted(counts.items(), key=lambda item: names[item[0]])
    ]


async def dashboard(session: AsyncSession, f: Filters, today: date) -> Dashboard:
    events_from = f.start or today
    events_to = f.end or today + timedelta(days=EVENT_DAYS)

    def members(status: PartyMemberStatus) -> Select:
        query = select(PartyMember.id).where(PartyMember.status == status)
        return _in_ward(query, PartyMember.ward_id, f)[0]

    query = (
        select(VolunteerProfile.interests)
        .join(PartyMember, PartyMember.id == VolunteerProfile.member_id)
        .where(
            VolunteerProfile.status == VolunteerStatus.ACTIVE,
            VolunteerProfile.campaign_id.is_(None),
        )
    )
    query, county = _in_ward(query, PartyMember.ward_id, f)
    volunteers = (await session.execute(query.add_columns(county))).all()

    query = select(Aspirant.id).where(Aspirant.status == AspirantStatus.APPROVED)
    aspirants = _in_area(Aspirant, query, f)[0]
    if f.seat:
        aspirants = aspirants.where(Aspirant.seat == f.seat)
    if f.aspirant:
        aspirants = aspirants.where(Aspirant.id == f.aspirant)

    nominee = (
        select(Aspirant.status)
        .where(Aspirant.campaign_id == Campaign.id)
        .correlate(Campaign)
        .scalar_subquery()
    )
    query, county = _campaigns(f, Campaign.seat, Campaign.kind, nominee)
    campaigns = (await session.execute(query.add_columns(county))).all()
    open_campaigns = sum(1 for _, kind, status, _ in campaigns if access.rule(kind, status).open)
    by_county_seat = Counter((county_id, seat) for seat, _, _, county_id in campaigns)

    # An event is placed by its own ward; seat and aspirant still act through its campaign.
    query = _campaigns(Filters(seat=f.seat, aspirant=f.aspirant), Campaign.seat)[0]
    query, county = _in_ward(query.join(Event, Event.campaign_id == Campaign.id), Event.ward_id, f)
    upcoming = (
        await session.execute(
            query.add_columns(county).where(
                Event.status == EventStatus.PLANNED,
                func.date(Event.scheduled_date) >= events_from,
                func.date(Event.scheduled_date) <= events_to,
            )
        )
    ).all()

    party = await _party_workspace(session, f, events_from, events_to)

    query = select(PartyMember.recruited_by_id, PartyMember.recruitment_county_id).where(
        PartyMember.recruited_by_id.is_not(None)
    )
    recruited = (await session.execute(_in_ward(query, PartyMember.ward_id, f)[0])).all()
    names_of = await session.execute(
        select(CampaignMember.id, User.first_name, User.last_name, User.username)
        .join(User, User.id == CampaignMember.user_id)
        .where(CampaignMember.id.in_({r for r, _ in recruited}))
    )
    recruiters = {
        member: f"{first} {last}".strip() or username
        for member, first, last, username in names_of.all()
    }

    ids = (
        {c for _, c in volunteers}
        | {c for c, _ in by_county_seat}
        | {c for _, c in upcoming}
        | {c for _, c in recruited if c is not None}
    )
    names = dict(
        (await session.execute(select(County.id, County.name).where(County.id.in_(ids)))).all()
    )
    interests = Counter(i for chosen, _ in volunteers for i in chosen)

    return Dashboard(
        approved_members=await _count(session, members(PartyMemberStatus.APPROVED)),
        pending_applications=await _count(session, members(PartyMemberStatus.PENDING)),
        active_volunteers=len(volunteers),
        volunteers_by_county=_by_county(Counter(c for _, c in volunteers), names),
        volunteers_by_interest=[
            InterestCount(interest=VolunteerArea(i), count=n) for i, n in sorted(interests.items())
        ],
        approved_aspirants=await _count(session, aspirants),
        active_campaigns=open_campaigns,
        events_from=events_from,
        events_to=events_to,
        upcoming_events_by_county=_by_county(Counter(c for _, c in upcoming), names),
        upcoming_events_by_seat=[
            SeatCount(seat=s, count=n) for s, n in sorted(Counter(s for s, _ in upcoming).items())
        ],
        campaigns_by_county_and_seat=[
            CountySeatCount(county_id=c, county=names[c], seat=s, count=n)
            for (c, s), n in sorted(
                by_county_seat.items(), key=lambda item: (names[item[0][0]], item[0][1])
            )
        ],
        party_workspace=party,
        applications_by_county=_by_county(Counter(c for _, c in recruited if c is not None), names),
        applications_by_coordinator=[
            CoordinatorCount(coordinator=recruiters[m], count=n)
            for m, n in sorted(
                Counter(m for m, _ in recruited).items(), key=lambda item: recruiters[item[0]]
            )
        ],
    )


async def _party_workspace(
    session: AsyncSession, f: Filters, events_from: date, events_to: date
) -> PartyWorkspaceTotals | None:
    """The party workspace's own counts in the place filter, or None before it exists."""
    found = await session.scalar(select(Campaign.id).where(Campaign.kind == WorkspaceKind.PARTY))
    if found is None:
        return None

    def mine(model) -> Select:
        return _in_ward(select(model.id).where(model.campaign_id == found), model.ward_id, f)[0]

    events = mine(Event).where(
        Event.status == EventStatus.PLANNED,
        func.date(Event.scheduled_date) >= events_from,
        func.date(Event.scheduled_date) <= events_to,
    )
    return PartyWorkspaceTotals(
        supporters=await _count(session, mine(Supporter)),
        mobilizers=await _count(session, mine(Mobilizer)),
        upcoming_events=await _count(session, events),
    )
