"""Which campaigns a caller may see, and which rows inside them."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Campaign,
    CampaignMember,
    Mobilizer,
    RegistrationCentre,
    User,
    UserRole,
)
from backend.services.membership import membership_refusal
from backend.services.targets import ward_in_area

NOTHING: frozenset[uuid.UUID] = frozenset()


async def visible_campaign_ids(session: AsyncSession, user: User) -> frozenset[uuid.UUID]:
    """The campaigns this caller works on.

    One join, the same for every role. A caller who is on no campaign reads
    nothing, which is what sends a new manager to set one up.
    """
    rows = await session.execute(
        select(CampaignMember.campaign_id).where(CampaignMember.user_id == user.id)
    )
    return frozenset(rows.scalars())


async def visible_user_ids(session: AsyncSession, user: User) -> frozenset[uuid.UUID]:
    """The people this caller shares a campaign with, plus the caller.

    A manager who has set nothing up yet sees only themselves, so the sign-up
    flow has no aspirant to offer and asks for a new one.
    """
    campaign_ids = await visible_campaign_ids(session, user)
    rows = await session.execute(
        select(CampaignMember.user_id).where(CampaignMember.campaign_id.in_(campaign_ids))
    )
    return frozenset({user.id, *rows.scalars()})


def limit_to_campaigns(statement: Select, column, campaign_ids: frozenset[uuid.UUID]) -> Select:
    """Narrow a query to the given ids. An empty set matches nothing, by design."""
    return statement.where(column.in_(campaign_ids))


async def require_visible_campaign(
    session: AsyncSession, user: User, campaign_id: uuid.UUID
) -> Campaign:
    """The campaign, or 404 when the caller has no business with it."""
    campaign = await session.get(Campaign, campaign_id)
    visible = await visible_campaign_ids(session, user)
    if campaign is None or campaign.id not in visible:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such campaign.")
    return campaign


async def add_member(
    session: AsyncSession, campaign_id: uuid.UUID, user_id: uuid.UUID
) -> CampaignMember:
    """Put somebody on a campaign, in the capacity their login carries.

    The place is taken from `users.role` and never passed in: every permission
    check reads that column, so a membership row saying anything else would
    name a capacity the member does not have.
    """
    existing = await session.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id
        )
    )
    if existing is not None:
        return existing

    named = await session.get(User, user_id)
    if named is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")
    refusal = await membership_refusal(session, named, campaign_id)
    if refusal is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, refusal)
    member = CampaignMember(campaign_id=campaign_id, user_id=user_id, role=named.role)
    session.add(member)
    await session.flush()
    return member


async def require_ward_in_campaign(
    session: AsyncSession,
    campaign: Campaign,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None = None,
) -> None:
    """A ward or centre named in a body has to lie inside the campaign's own seat.

    The ids arrive from the client. Without this a row lands in a ward the
    campaign has no target for, where no strategy read counts it.
    """
    if ward_id is not None and not await ward_in_area(session, campaign, ward_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That ward is not one this campaign works."
        )
    if centre_id is not None:
        centre_ward = await session.scalar(
            select(RegistrationCentre.ward_id).where(RegistrationCentre.id == centre_id)
        )
        if centre_ward is None or centre_ward != ward_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "That registration centre is not in that ward."
            )


async def require_campaign_mobilizer(
    session: AsyncSession, campaign_id: uuid.UUID, mobilizer_id: uuid.UUID | None
) -> None:
    """A named mobilizer must be one of this campaign's own.

    Every route that takes a mobilizer id in its body has to say so, or a caller
    hangs another campaign's organizer off their own rows.
    """
    if mobilizer_id is None:
        return
    owner = await session.scalar(select(Mobilizer.campaign_id).where(Mobilizer.id == mobilizer_id))
    if owner != campaign_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such mobilizer on this campaign.")


def require_own_ward(user: User, ward_id: uuid.UUID) -> None:
    """Stop a mobilizer writing into somebody else's ward."""
    if user.role is not UserRole.MOBILIZER:
        return
    profile = user.mobilizer_profile
    if profile is None or profile.ward_id != ward_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "A mobilizer may only work in their own ward."
        )


async def mobilizer_profile_for(session: AsyncSession, user: User) -> Mobilizer | None:
    """The caller's own mobilizer row."""
    if user.role is not UserRole.MOBILIZER:
        return None
    return user.mobilizer_profile
