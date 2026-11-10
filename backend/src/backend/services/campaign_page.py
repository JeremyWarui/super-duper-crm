"""An aspirant installation's candidate page: the standalone campaign's profile, shown as the
website's homepage, edited from the workspace, and signing volunteers up for the campaign."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    CandidateProfile,
    Constituency,
    User,
    Ward,
    WorkspaceKind,
)
from backend.schemas.candidates import (
    CandidateDetail,
    CandidateVolunteerCreate,
    ProfileRead,
    ProfileWrite,
)
from backend.schemas.party import MemberPlace
from backend.services import campaign_volunteers
from backend.services.audit import record
from backend.services.consent import CAMPAIGN_VOLUNTEER_WORDING
from backend.services.errors import NotFound
from backend.services.targets import wards_in_area

PLACES = (
    selectinload(Campaign.candidate),
    selectinload(Campaign.county),
    selectinload(Campaign.constituency).selectinload(Constituency.county),
    selectinload(Campaign.ward).selectinload(Ward.constituency).selectinload(Constituency.county),
)


async def campaign(session: AsyncSession) -> Campaign:
    """The installation's one standalone campaign; NotFound before setup makes it."""
    found = await session.scalar(
        select(Campaign).where(Campaign.kind == WorkspaceKind.STANDALONE).options(*PLACES)
    )
    if found is None:
        raise NotFound("This site has no campaign yet.")
    return found


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
    candidate = found.candidate
    area = found.area
    return CandidateDetail(
        slug="",
        name=candidate.display_name if candidate else found.title,
        seat=found.seat,
        area=area.name if area is not None else "",
        county=found.county_name,
        photo_url=profile.photo_url,
        slogan=profile.slogan,
        bio=profile.bio,
        priorities=profile.priorities,
        office_address=profile.office_address,
        office_phone=profile.office_phone,
        office_email=profile.office_email,
        events=[],
        volunteering_open=True,
        consent_wording=CAMPAIGN_VOLUNTEER_WORDING,
        wards=[MemberPlace(id=w.id, name=w.name) for w in await wards_in_area(session, found)],
    )


async def read(session: AsyncSession) -> ProfileRead:
    profile = await _profile(session, await campaign(session))
    if profile is None:
        return ProfileRead()
    return ProfileRead.model_validate(profile, from_attributes=True)


async def write(session: AsyncSession, payload: ProfileWrite, *, actor: User) -> ProfileRead:
    """Replace the candidate page, made on first save; audited."""
    found = await campaign(session)
    profile = await _profile(session, found)
    values = payload.model_dump()
    if profile is None:
        profile = CandidateProfile(campaign_id=found.id, **values)
        session.add(profile)
    else:
        for name, value in values.items():
            setattr(profile, name, value)
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
    return ProfileRead.model_validate(profile, from_attributes=True)


async def sign_up(session: AsyncSession, payload: CandidateVolunteerCreate) -> str:
    """Sign a volunteer up for the campaign; refused while the page is unpublished."""
    await public_page(session)
    return await campaign_volunteers.sign_up(session, await campaign(session), payload)
