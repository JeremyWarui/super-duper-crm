"""Candidate profiles: the website editor writes them, the public site lists the published ones,
and a candidate's page signs volunteers up for that candidate's campaign."""

import re
import uuid
from datetime import date

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_or_refuse, replace_fields
from backend.models import (
    Aspirant,
    AspirantStatus,
    Campaign,
    CandidateProfile,
    Constituency,
    PartyPost,
    PostKind,
    User,
    Ward,
    party_post_aspirants,
)
from backend.schemas.candidates import (
    CandidateAdminRead,
    CandidateCard,
    CandidateDetail,
    CandidateEvent,
    CandidateVolunteerCreate,
    ProfileRead,
    ProfileWrite,
)
from backend.schemas.party import MemberPlace
from backend.services import access, campaign_volunteers
from backend.services.audit import record
from backend.services.consent import CAMPAIGN_VOLUNTEER_WORDING
from backend.services.errors import NotFound, Refused
from backend.services.targets import wards_in_area

PLACES = (
    selectinload(Aspirant.member),
    selectinload(Aspirant.county),
    selectinload(Aspirant.constituency).selectinload(Constituency.county),
    selectinload(Aspirant.ward).selectinload(Ward.constituency).selectinload(Constituency.county),
)


def _county_id(aspirant: Aspirant) -> uuid.UUID | None:
    if aspirant.county_id:
        return aspirant.county_id
    if aspirant.constituency:
        return aspirant.constituency.county_id
    return aspirant.ward.constituency.county_id if aspirant.ward else None


def slug(aspirant: Aspirant) -> str:
    """`mp-westlands-1a2b3c4d`: the seat, the area and the start of the aspirant's id."""
    area = re.sub(r"[^a-z0-9]+", "-", aspirant.area_name.lower()).strip("-")
    return f"{aspirant.seat.value.replace('_', '-')}-{area}-{aspirant.id.hex[:8]}"


def _card(aspirant: Aspirant, profile: CandidateProfile) -> dict:
    return {
        "slug": slug(aspirant),
        "name": aspirant.member.full_name,
        "seat": aspirant.seat,
        "area": aspirant.area_name,
        "county": aspirant.county_name,
        "photo_url": profile.photo_url,
        "slogan": profile.slogan,
    }


async def _listed(session: AsyncSession) -> list[tuple[Aspirant, CandidateProfile]]:
    rows = await session.execute(
        select(Aspirant, CandidateProfile)
        .join(CandidateProfile, CandidateProfile.aspirant_id == Aspirant.id)
        .where(Aspirant.status == AspirantStatus.APPROVED, CandidateProfile.published.is_(True))
        .options(*PLACES)
    )
    return list(rows.tuples())


async def candidates(
    session: AsyncSession,
    *,
    seat: str | None = None,
    county: uuid.UUID | None = None,
    q: str = "",
) -> list[CandidateCard]:
    """Approved aspirants with a published profile, by name."""
    needle = q.strip().lower()
    out = []
    for aspirant, profile in await _listed(session):
        if seat and aspirant.seat.value != seat:
            continue
        if county and _county_id(aspirant) != county:
            continue
        card = _card(aspirant, profile)
        if needle and needle not in card["name"].lower() and needle not in card["area"].lower():
            continue
        out.append(CandidateCard(**card))
    return sorted(out, key=lambda c: c.name.lower())


async def _by_slug(session: AsyncSession, value: str) -> tuple[Aspirant, CandidateProfile]:
    for aspirant, profile in await _listed(session):
        if slug(aspirant) == value:
            return aspirant, profile
    raise NotFound("No such candidate.")


async def _volunteer_campaign(session: AsyncSession, aspirant: Aspirant) -> Campaign | None:
    """The listed aspirant's campaign, when the party has made one and it is open."""
    if aspirant.campaign_id is None:
        return None
    if not (await access.workspace_access(session, aspirant.campaign_id)).open:
        return None
    return await session.get(Campaign, aspirant.campaign_id)


async def candidate(session: AsyncSession, value: str, today: date) -> CandidateDetail:
    """One listed candidate's page: profile, upcoming party events naming them, the form."""
    aspirant, profile = await _by_slug(session, value)
    events = await session.scalars(
        select(PartyPost)
        .join(party_post_aspirants, party_post_aspirants.c.post_id == PartyPost.id)
        .where(
            party_post_aspirants.c.aspirant_id == aspirant.id,
            PartyPost.kind == PostKind.EVENT,
            PartyPost.published.is_(True),
            PartyPost.event_date >= today,
        )
        .order_by(PartyPost.event_date)
    )
    campaign = await _volunteer_campaign(session, aspirant)
    wards = await wards_in_area(session, campaign) if campaign else []
    return CandidateDetail(
        **_card(aspirant, profile),
        **profile_fields(profile),
        events=[
            CandidateEvent(id=e.id, title=e.title, event_date=e.event_date, venue=e.venue)
            for e in events
        ],
        volunteering_open=campaign is not None,
        consent_wording=CAMPAIGN_VOLUNTEER_WORDING,
        wards=[MemberPlace(id=w.id, name=w.name) for w in wards],
    )


async def sign_up(session: AsyncSession, value: str, payload: CandidateVolunteerCreate) -> str:
    """Add a volunteer to the candidate's campaign; returns a withdrawal code either way."""
    aspirant, _ = await _by_slug(session, value)
    campaign = await _volunteer_campaign(session, aspirant)
    if campaign is None:
        raise Refused("This candidate is not taking volunteers.")
    return await campaign_volunteers.sign_up(session, campaign, payload)


def profile_read(profile: CandidateProfile | None) -> ProfileRead:
    """A profile as the editor reads it; an empty one before the first save."""
    if profile is None:
        return ProfileRead()
    return ProfileRead.model_validate(profile, from_attributes=True)


def profile_fields(profile: CandidateProfile) -> dict:
    """The page's text from the profile, as `CandidateDetail` takes it."""
    return {
        "bio": profile.bio,
        "priorities": profile.priorities,
        "office_address": profile.office_address,
        "office_phone": profile.office_phone,
        "office_email": profile.office_email,
    }


def save_profile(
    session: AsyncSession, profile: CandidateProfile | None, values: dict, **keys: object
) -> CandidateProfile:
    """Replace a profile's fields, or add one with `keys` when there is none yet."""
    if profile is None:
        profile = CandidateProfile(**keys, **values)
        session.add(profile)
    else:
        replace_fields(profile, values)
    return profile


async def _approved(session: AsyncSession, aspirant_id: uuid.UUID) -> Aspirant:
    aspirant = await session.scalar(
        select(Aspirant).where(Aspirant.id == aspirant_id).options(*PLACES)
    )
    if aspirant is None:
        raise NotFound("No such aspirant.")
    if aspirant.status is not AspirantStatus.APPROVED:
        raise Refused("Only an approved aspirant gets a profile.")
    return aspirant


def _admin_read(aspirant: Aspirant, profile: CandidateProfile | None) -> CandidateAdminRead:
    return CandidateAdminRead(
        aspirant_id=aspirant.id,
        name=aspirant.member.full_name,
        seat=aspirant.seat,
        area=aspirant.area_name,
        profile=profile_read(profile),
    )


async def approved_with_profiles(session: AsyncSession) -> list[CandidateAdminRead]:
    """Every approved aspirant, with the profile written so far, for the website editor."""
    rows = await session.execute(
        select(Aspirant, CandidateProfile)
        .outerjoin(CandidateProfile, CandidateProfile.aspirant_id == Aspirant.id)
        .where(Aspirant.status == AspirantStatus.APPROVED)
        .options(*PLACES)
    )
    out = [_admin_read(a, p) for a, p in rows.tuples()]
    return sorted(out, key=lambda c: c.name.lower())


async def _profile(session: AsyncSession, aspirant_id: uuid.UUID) -> CandidateProfile | None:
    return await session.scalar(
        select(CandidateProfile).where(CandidateProfile.aspirant_id == aspirant_id)
    )


async def read_profile(session: AsyncSession, aspirant_id: uuid.UUID) -> CandidateAdminRead:
    aspirant = await _approved(session, aspirant_id)
    return _admin_read(aspirant, await _profile(session, aspirant_id))


async def write_profile(
    session: AsyncSession, aspirant_id: uuid.UUID, payload: ProfileWrite, *, actor: User
) -> CandidateAdminRead:
    aspirant = await _approved(session, aspirant_id)
    if aspirant.campaign_id is None:
        raise Refused("Create this aspirant's workspace before writing their page.")
    profile = await _profile(session, aspirant_id)
    profile = save_profile(
        session,
        profile,
        payload.model_dump(),
        campaign_id=aspirant.campaign_id,
        aspirant_id=aspirant_id,
    )
    record(
        session,
        actor=actor,
        action="party.candidate_profile.write",
        subject_type="candidate_profile",
        subject_id=aspirant_id,
        detail={"published": payload.published},
    )
    await session.commit()
    await session.refresh(profile)
    return _admin_read(aspirant, profile)


async def post_aspirants(session: AsyncSession, post_id: uuid.UUID) -> list[uuid.UUID]:
    await get_or_refuse(session, PartyPost, post_id, "post")
    return list(
        await session.scalars(
            select(party_post_aspirants.c.aspirant_id).where(
                party_post_aspirants.c.post_id == post_id
            )
        )
    )


async def set_post_aspirants(
    session: AsyncSession, post_id: uuid.UUID, aspirant_ids: list[uuid.UUID], *, actor: User
) -> list[uuid.UUID]:
    """Replace the aspirants an event names; each must be an approved aspirant."""
    post = await get_or_refuse(session, PartyPost, post_id, "post")
    if post.kind is not PostKind.EVENT:
        raise Refused("Only an event names aspirants.")
    wanted = set(aspirant_ids)
    approved = set(
        await session.scalars(
            select(Aspirant.id).where(
                Aspirant.id.in_(wanted), Aspirant.status == AspirantStatus.APPROVED
            )
        )
    )
    if approved != wanted:
        raise Refused("An event can name only approved aspirants.")
    await session.execute(
        delete(party_post_aspirants).where(party_post_aspirants.c.post_id == post_id)
    )
    if wanted:
        await session.execute(
            insert(party_post_aspirants),
            [{"post_id": post_id, "aspirant_id": a} for a in wanted],
        )
    record(
        session,
        actor=actor,
        action="party.post.aspirants",
        subject_type="party_post",
        subject_id=post_id,
        detail={"count": len(wanted)},
    )
    await session.commit()
    return sorted(wanted)
