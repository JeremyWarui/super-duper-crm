"""What a caller may read and write: their own campaign, and within it how far their role
reaches with the action (`services/permissions.py`)."""

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from backend.api.deps import CurrentUser, SessionDep
from backend.models import (
    Agent,
    Campaign,
    CampaignMember,
    CampaignMemberArea,
    Mobilizer,
    OperationalGrain,
    RegistrationCentre,
    User,
    UserRole,
)
from backend.services.accounts import campaign_mobilizer
from backend.services.errors import Forbidden, NotFound, Refused
from backend.services.permissions import Area, Reach, narrow, reach
from backend.services.targets import require_targeted, require_ward

# An id no row has, for a caller with nothing of their own.
NOBODY = uuid.UUID(int=0)


async def own_ids(session: AsyncSession, user: User) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """A mobilizer's own mobilizer id, or anyone else's agent id; NOBODY when they have none."""
    if user.role is UserRole.MOBILIZER:
        profile = user.mobilizer_profile
        return (profile.id if profile is not None else NOBODY), None
    agent = await session.scalar(select(Agent.id).where(Agent.user_id == user.id))
    return None, agent or NOBODY


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
    if profile is None or profile.ward_id is None:
        return NOBODY
    return profile.ward_id


async def area_ids(session: AsyncSession, user: User) -> Area:
    """The wards and centres in the caller's `campaign_member_areas`."""
    rows = (
        await session.execute(
            select(CampaignMemberArea.ward_id, CampaignMemberArea.registration_centre_id)
            .join(CampaignMember, CampaignMember.id == CampaignMemberArea.campaign_member_id)
            .where(CampaignMember.user_id == user.id)
        )
    ).all()
    return Area(
        frozenset(ward for ward, _ in rows if ward is not None),
        frozenset(centre for _, centre in rows if centre is not None),
    )


async def area_of(session: AsyncSession, user: User, action: str) -> Area | None:
    """Where the caller may do this action inside their campaign; None for everywhere."""
    match reach(user, action):
        case Reach.ALL:
            return None
        case Reach.AREA:
            return await area_ids(session, user)
        case Reach.OWN if user.role is UserRole.MOBILIZER:
            return Area(frozenset({mobilizer_ward_id(user) or NOBODY}), frozenset())
        case _:
            return Area(frozenset(), frozenset())


def own_ground_row(user: User, campaign_id: uuid.UUID) -> Mobilizer | None:
    """The caller's own mobilizer row on this campaign."""
    if user.role is not UserRole.MOBILIZER:
        return None
    profile = user.mobilizer_profile
    return profile if profile is not None and profile.campaign_id == campaign_id else None


async def scoped(
    session: AsyncSession,
    user: User,
    statement: Select,
    model: type,
    campaign: uuid.UUID | None,
    action: str,
) -> Select:
    """Narrow a query on a campaign's rows to the caller's campaign and their reach in it."""
    if campaign is not None:
        statement = statement.where(model.campaign_id == campaign)
    statement = statement.where(model.campaign_id.in_(await visible_campaign_ids(session, user)))
    return narrow(statement, await area_of(session, user, action), model)


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
        raise NotFound("No such campaign.")
    return campaign


async def visible_campaign(
    campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Campaign:
    """The path's campaign, once the caller may see it."""
    return await require_visible_campaign(session, user, campaign_id)


VisibleCampaign = Annotated[Campaign, Depends(visible_campaign)]


async def require_visible(
    session: AsyncSession,
    user: User,
    model: type,
    row_id: uuid.UUID,
    noun: str,
    action: str,
    options: Sequence[ORMOption] = (),
):
    """A row on the caller's campaign and inside their reach; otherwise 404 or 403.

    A row with no ward is outside every area.
    """
    row = await load(session, model, row_id, options)
    if row is None:
        raise NotFound(f"No such {noun}.")
    await require_visible_campaign(session, user, row.campaign_id)
    await require_in_area(
        session, user, action, row.ward_id, getattr(row, "registration_centre_id", None)
    )
    return row


async def require_in_area(
    session: AsyncSession,
    user: User,
    action: str,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None = None,
) -> None:
    """403 for a place outside the caller's reach with this action, a missing ward included."""
    area = await area_of(session, user, action)
    if area is None or area.holds(ward_id, centre_id):
        return
    if user.role is UserRole.MOBILIZER:
        raise Forbidden("A mobilizer may only work in their own ward.")
    raise Forbidden("That is outside your area.")


async def require_mobilizer_in_area(
    session: AsyncSession, user: User, action: str, mobilizer_id: uuid.UUID | None
) -> None:
    """403 when a mobilizer named in a body works outside the caller's reach with this action."""
    if mobilizer_id is None:
        return
    mobilizer = await session.get(Mobilizer, mobilizer_id)
    if mobilizer is not None:
        await require_in_area(
            session, user, action, mobilizer.ward_id, mobilizer.registration_centre_id
        )


async def require_ward_in_campaign(
    session: AsyncSession,
    campaign: Campaign,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None = None,
) -> None:
    """A ward, and a centre in it, must lie inside the campaign's seat."""
    if ward_id is not None:
        await require_ward(session, campaign, ward_id)
    if centre_id is not None:
        centre_ward = await session.scalar(
            select(RegistrationCentre.ward_id).where(RegistrationCentre.id == centre_id)
        )
        if centre_ward is None or centre_ward != ward_id:
            raise Refused("That registration centre is not in that ward.")


def require_centre_in_ward_race(campaign: Campaign, centre_id: uuid.UUID | None) -> None:
    """In a ward (MCA) race a registration centre is required."""
    if campaign.operational_grain is OperationalGrain.CENTRE and centre_id is None:
        raise Refused("In an MCA race this happens at a registration centre; pick one.")


async def require_place(
    session: AsyncSession,
    user: User,
    action: str,
    campaign_id: uuid.UUID,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None,
) -> Campaign:
    """The campaign, once the caller may see it, the place is in their area and the campaign's
    seat, and an MCA race has its centre."""
    campaign = await require_visible_campaign(session, user, campaign_id)
    await require_in_area(session, user, action, ward_id, centre_id)
    await require_ward_in_campaign(session, campaign, ward_id, centre_id)
    require_centre_in_ward_race(campaign, centre_id)
    return campaign


async def require_targeted_centre(
    session: AsyncSession, campaign: Campaign, centre_id: uuid.UUID | None
) -> None:
    """A centre a supporter is filed at must have a target, or they count toward nothing."""
    if centre_id is None or campaign.operational_grain is not OperationalGrain.CENTRE:
        return
    await require_targeted(session, campaign.id, centre_id)


async def require_campaign_mobilizer(
    session: AsyncSession, campaign_id: uuid.UUID, mobilizer_id: uuid.UUID | None
) -> None:
    """A mobilizer named in a body must belong to this campaign."""
    if mobilizer_id is not None:
        await campaign_mobilizer(session, campaign_id, mobilizer_id)
