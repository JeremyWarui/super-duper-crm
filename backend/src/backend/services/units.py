"""A campaign's unit of work, the whole campaign, a ward, or (in an MCA race) a registration
centre, and the logins in it. Calls and announcements both reach a unit."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    Agent,
    CampaignMember,
    CampaignMemberArea,
    Constituency,
    Mobilizer,
    RegistrationCentre,
    UserRole,
    Ward,
)
from backend.services.errors import Refused

# Every unit's team includes these.
LEADS = (UserRole.CANDIDATE, UserRole.MANAGER, UserRole.COMMS)


async def resolve(
    session: AsyncSession, ward_id: uuid.UUID | None, centre_id: uuid.UUID | None
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """The unit's ward and centre; a centre brings its own ward. The place must lie inside the
    campaign's seat (`api.scope.require_ward_in_campaign` checks that)."""
    if centre_id is None:
        return ward_id, None
    centre_ward = await session.scalar(
        select(RegistrationCentre.ward_id).where(RegistrationCentre.id == centre_id)
    )
    if centre_ward is None or (ward_id is not None and ward_id != centre_ward):
        raise Refused("That registration centre is not in that ward.")
    return centre_ward, centre_id


async def logins(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    ward_id: uuid.UUID | None,
    centre_id: uuid.UUID | None = None,
) -> list[uuid.UUID]:
    """The unit's team: every login of the campaign; or for a ward or centre, the leads, the
    coordinators whose area holds it (by its centre, ward, constituency or county), and the
    mobilizers and agents working there who are still on the campaign."""
    members = select(CampaignMember.user_id).where(CampaignMember.campaign_id == campaign_id)
    if ward_id is None:
        return list(dict.fromkeys(await session.scalars(members)))
    constituency_id, county_id = (
        await session.execute(
            select(Ward.constituency_id, Constituency.county_id)
            .join(Constituency, Constituency.id == Ward.constituency_id)
            .where(Ward.id == ward_id)
        )
    ).one()
    area = or_(
        CampaignMemberArea.ward_id == ward_id,
        CampaignMemberArea.constituency_id == constituency_id,
        CampaignMemberArea.county_id == county_id,
    )
    if centre_id is not None:
        area = or_(area, CampaignMemberArea.registration_centre_id == centre_id)
    coordinators = (
        select(CampaignMember.user_id)
        .join(CampaignMemberArea, CampaignMemberArea.campaign_member_id == CampaignMember.id)
        .where(CampaignMember.campaign_id == campaign_id, area)
    )
    mobilizers = select(Mobilizer.user_id).where(
        Mobilizer.campaign_id == campaign_id, Mobilizer.user_id.in_(members)
    )
    agents = select(Agent.user_id).where(
        Agent.campaign_id == campaign_id, Agent.user_id.in_(members)
    )
    if centre_id is None:
        mobilizers = mobilizers.where(Mobilizer.ward_id == ward_id)
        agents = agents.where(Agent.ward_id == ward_id)
    else:
        mobilizers = mobilizers.where(Mobilizer.registration_centre_id == centre_id)
        agents = agents.where(Agent.registration_centre_id == centre_id)
    leads = members.where(CampaignMember.role.in_(LEADS))
    found = await session.scalars(leads.union(coordinators, mobilizers, agents))
    return list(dict.fromkeys(found))


WHOLE_CAMPAIGN = "Whole campaign"


async def labels(
    session: AsyncSession, places: list[tuple[uuid.UUID | None, uuid.UUID | None]]
) -> dict[tuple[uuid.UUID | None, uuid.UUID | None], str]:
    """A name for each (ward, centre) unit: the centre's name, the ward's, or the whole campaign."""
    ward_ids = {w for w, _ in places if w is not None}
    centre_ids = {c for _, c in places if c is not None}
    wards = (
        dict((await session.execute(select(Ward.id, Ward.name).where(Ward.id.in_(ward_ids)))).all())
        if ward_ids
        else {}
    )
    centres = (
        dict(
            (
                await session.execute(
                    select(RegistrationCentre.id, RegistrationCentre.name).where(
                        RegistrationCentre.id.in_(centre_ids)
                    )
                )
            ).all()
        )
        if centre_ids
        else {}
    )
    out = {}
    for ward, centre in places:
        if centre is not None:
            out[(ward, centre)] = f"{centres.get(centre, 'A centre')} centre"
        elif ward is not None:
            out[(ward, centre)] = f"{wards.get(ward, 'A')} ward"
        else:
            out[(ward, centre)] = WHOLE_CAMPAIGN
    return out
