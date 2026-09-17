"""What a caller may read and write: their own campaign, and a mobilizer's own ward."""

import uuid
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from backend.models import Campaign, CampaignMember, Mobilizer, RegistrationCentre, User, UserRole
from backend.services.targets import ward_in_area


async def visible_campaign_ids(session: AsyncSession, user: User) -> frozenset[uuid.UUID]:
    rows = await session.execute(
        select(CampaignMember.campaign_id).where(CampaignMember.user_id == user.id)
    )
    return frozenset(rows.scalars())


async def visible_user_ids(session: AsyncSession, user: User) -> frozenset[uuid.UUID]:
    """The people on the caller's campaign, and the caller."""
    campaign_ids = await visible_campaign_ids(session, user)
    rows = await session.execute(
        select(CampaignMember.user_id).where(CampaignMember.campaign_id.in_(campaign_ids))
    )
    return frozenset({user.id, *rows.scalars()})


def mobilizer_ward_id(user: User) -> uuid.UUID | None:
    """A mobilizer's own ward, a ward matching nothing without one, or None for other roles.

    Needs `User.mobilizer_profile` loaded.
    """
    if user.role is not UserRole.MOBILIZER:
        return None
    profile = user.mobilizer_profile
    return profile.ward_id if profile is not None else uuid.UUID(int=0)


def own_ground_row(user: User, campaign_id: uuid.UUID) -> Mobilizer | None:
    """The caller's own mobilizer row on this campaign."""
    if user.role is not UserRole.MOBILIZER:
        return None
    profile = user.mobilizer_profile
    return profile if profile is not None and profile.campaign_id == campaign_id else None


async def scoped(
    session: AsyncSession, user: User, statement: Select, model: type, campaign: uuid.UUID | None
) -> Select:
    """Narrow a query on a campaign's rows to the caller's campaign and, for a mobilizer, ward."""
    if campaign is not None:
        statement = statement.where(model.campaign_id == campaign)
    statement = statement.where(model.campaign_id.in_(await visible_campaign_ids(session, user)))
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None:
        statement = statement.where(model.ward_id == own_ward)
    return statement


async def all_rows(session: AsyncSession, statement: Select) -> list:
    return list((await session.execute(statement)).scalars().all())


async def load(
    session: AsyncSession, model: type, row_id: uuid.UUID, options: Sequence[ORMOption] = ()
):
    """A row by id with its relationships loaded, or None."""
    return (
        await session.execute(select(model).where(model.id == row_id).options(*options))
    ).scalar_one_or_none()


async def require_visible_campaign(
    session: AsyncSession, user: User, campaign_id: uuid.UUID
) -> Campaign:
    """The caller's campaign, or 404."""
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None or campaign.id not in await visible_campaign_ids(session, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such campaign.")
    return campaign


async def require_visible(
    session: AsyncSession,
    user: User,
    model: type,
    row_id: uuid.UUID,
    noun: str,
    options: Sequence[ORMOption] = (),
):
    """A row on the caller's campaign and, for a mobilizer, in their ward; otherwise 404 or 403."""
    row = await load(session, model, row_id, options)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No such {noun}.")
    await require_visible_campaign(session, user, row.campaign_id)
    if row.ward_id is not None:
        require_own_ward(user, row.ward_id)
    return row


def require_own_ward(user: User, ward_id: uuid.UUID) -> None:
    own_ward = mobilizer_ward_id(user)
    if own_ward is not None and own_ward != ward_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "A mobilizer may only work in their own ward."
        )


async def require_ward_in_campaign(
    session: AsyncSession,
    campaign: Campaign,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None = None,
) -> None:
    """A ward, and a centre in it, must lie inside the campaign's seat."""
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
    """A mobilizer named in a body must belong to this campaign."""
    if mobilizer_id is None:
        return
    owner = await session.scalar(select(Mobilizer.campaign_id).where(Mobilizer.id == mobilizer_id))
    if owner != campaign_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No such mobilizer on this campaign.")
