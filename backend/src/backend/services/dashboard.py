"""Party-wide counts for the superuser's dashboard.

A place filter keeps members and volunteers living in it, and campaigns, aspirants and
events whose own area lies inside it. `seat` and `aspirant` act through the campaign.
Only counts and county names leave; no campaign record's text does.
"""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import ColumnElement, Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.models import (
    AccessState,
    Aspirant,
    AspirantStatus,
    Campaign,
    CampaignSubscription,
    Constituency,
    County,
    EntryKind,
    Event,
    EventStatus,
    PartyMember,
    PartyMemberStatus,
    Seat,
    SubscriptionEntry,
    VolunteerInterest,
    VolunteerProfile,
    VolunteerStatus,
    Ward,
)
from backend.schemas.dashboard import (
    CountyCount,
    CountySeatCount,
    Dashboard,
    DashboardRevenue,
    InterestCount,
    SeatCount,
)
from backend.services.billing import access, lapse_days

EVENT_DAYS = 30
ANSWERING = frozenset({AccessState.ACTIVE, AccessState.GRACE_PERIOD, AccessState.READ_ONLY})
PAID = frozenset({AccessState.ACTIVE, AccessState.GRACE_PERIOD})


@dataclass(frozen=True)
class Filters:
    county: uuid.UUID | None = None
    constituency: uuid.UUID | None = None
    ward: uuid.UUID | None = None
    seat: Seat | None = None
    aspirant: uuid.UUID | None = None
    start: date | None = None
    end: date | None = None

    @property
    def narrows_campaigns(self) -> bool:
        return any((self.county, self.constituency, self.ward, self.seat, self.aspirant))


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
    """The campaigns the filters keep; returns the query and the campaign's county id."""
    query, county = _in_area(Campaign, select(*columns).select_from(Campaign), f)
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
    revenue_from = f.start or date(today.year, 1, 1)
    revenue_to = f.end or date(today.year, 12, 31)

    def members(status: PartyMemberStatus) -> Select:
        query = select(PartyMember.id).where(PartyMember.status == status)
        return _in_ward(query, PartyMember.ward_id, f)[0]

    query = (
        select(VolunteerProfile.interests)
        .join(PartyMember, PartyMember.id == VolunteerProfile.member_id)
        .where(VolunteerProfile.status == VolunteerStatus.ACTIVE)
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
    query, county = _campaigns(
        f, Campaign.seat, nominee, CampaignSubscription.paid_until, CampaignSubscription.hold
    )
    query = query.outerjoin(CampaignSubscription, CampaignSubscription.campaign_id == Campaign.id)
    campaigns = (await session.execute(query.add_columns(county))).all()
    lapse = await lapse_days(session)
    # A campaign with no subscription row is locked, so it is neither answering nor paid.
    states = [
        (status, access(paid_until, hold, today, *lapse).state if hold is not None else None)
        for _, status, paid_until, hold, _ in campaigns
    ]
    answering = sum(
        1
        for status, state in states
        if state in ANSWERING and status in (None, AspirantStatus.APPROVED)
    )
    paid = sum(1 for _, state in states if state in PAID)
    by_county_seat = Counter((county_id, seat) for seat, _, _, _, county_id in campaigns)

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

    live = and_(
        SubscriptionEntry.kind == EntryKind.PAYMENT,
        SubscriptionEntry.voided_at.is_(None),
        SubscriptionEntry.received_on >= revenue_from,
        SubscriptionEntry.received_on <= revenue_to,
    )
    query = _campaigns(f, SubscriptionEntry.amount_kes)[0]
    query = (
        query.join(CampaignSubscription, CampaignSubscription.campaign_id == Campaign.id)
        .join(SubscriptionEntry, SubscriptionEntry.subscription_id == CampaignSubscription.id)
        .where(live)
    )
    amounts = list(await session.scalars(query))
    if not f.narrows_campaigns:
        closed = (
            select(SubscriptionEntry.amount_kes)
            .join(
                CampaignSubscription, CampaignSubscription.id == SubscriptionEntry.subscription_id
            )
            .where(live, CampaignSubscription.campaign_id.is_(None))
        )
        amounts += list(await session.scalars(closed))

    ids = {c for _, c in volunteers} | {c for c, _ in by_county_seat} | {c for _, c in upcoming}
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
            InterestCount(interest=VolunteerInterest(i), count=n)
            for i, n in sorted(interests.items())
        ],
        approved_aspirants=await _count(session, aspirants),
        active_campaigns=answering,
        active_subscriptions=paid,
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
        revenue=DashboardRevenue(
            start=revenue_from, end=revenue_to, total_kes=sum(amounts), count=len(amounts)
        ),
    )
