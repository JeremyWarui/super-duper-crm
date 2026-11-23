"""The candidate page: the campaign's profile, shown as the website's homepage, edited from the
workspace, and signing volunteers up for the campaign."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import replace_fields
from backend.models import (
    Campaign,
    CandidateProfile,
    Constituency,
    User,
    Ward,
)
from backend.schemas.candidates import (
    CandidateDetail,
    CandidateVolunteerCreate,
    ProfileRead,
    ProfileWrite,
)
from backend.schemas.common import Named
from backend.services import campaign_volunteers
from backend.services.audit import record
from backend.services.consent import CAMPAIGN_VOLUNTEER_WORDING
from backend.services.errors import NotFound
from backend.services.targets import ward_choices

PLACES = (
    selectinload(Campaign.candidate),
    selectinload(Campaign.county),
    selectinload(Campaign.constituency).selectinload(Constituency.county),
    selectinload(Campaign.ward).selectinload(Ward.constituency).selectinload(Constituency.county),
)


async def campaign(session: AsyncSession) -> Campaign:
    """The installation's campaign; NotFound before setup makes it."""
    found = await session.scalar(
        select(Campaign).order_by(Campaign.created_at).limit(1).options(*PLACES)
    )
    if found is None:
        raise NotFound("This site has no campaign yet.")
    return found


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


async def _profile(session: AsyncSession, found: Campaign) -> CandidateProfile | None:
    return await session.scalar(
        select(CandidateProfile).where(CandidateProfile.campaign_id == found.id)
    )


async def public_page(session: AsyncSession) -> CandidateDetail:
    """The published page with the volunteer form's wards; NotFound while unpublished."""
    found = await campaign(session)
    profile = await _profile(session, found)
    if profile is None or not profile.published:
        raise NotFound("The candidate page is not published yet.")
    return CandidateDetail(
        slug="",
        name=found.candidate_label or found.title,
        seat=found.seat,
        area=found.area_label,
        county=found.county_name,
        photo_url=profile.photo_url,
        slogan=profile.slogan,
        **profile_fields(profile),
        events=[],
        volunteering_open=True,
        consent_wording=CAMPAIGN_VOLUNTEER_WORDING,
        national=found.national,
        wards=[Named(id=w.id, name=w.name) for w in await ward_choices(session, found)],
    )


async def read(session: AsyncSession) -> ProfileRead:
    return profile_read(await _profile(session, await campaign(session)))


async def write(session: AsyncSession, payload: ProfileWrite, *, actor: User) -> ProfileRead:
    """Replace the candidate page, made on first save; audited."""
    found = await campaign(session)
    profile = await _profile(session, found)
    if profile is None:
        profile = CandidateProfile(campaign_id=found.id, **payload.model_dump())
        session.add(profile)
    else:
        replace_fields(profile, payload.model_dump())
    record(
        session,
        actor=actor,
        action="campaign.candidate_page.write",
        subject_type="campaign",
        subject_id=found.id,
        campaign_id=found.id,
        detail={"published": payload.published},
    )
    await session.commit()
    return profile_read(profile)


async def sign_up(session: AsyncSession, payload: CandidateVolunteerCreate) -> str:
    """Sign a volunteer up for the campaign; refused while the page is unpublished."""
    await public_page(session)
    return await campaign_volunteers.sign_up(session, await campaign(session), payload)
