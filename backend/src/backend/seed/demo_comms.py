"""The texting demo (DM-7): two consenting contacts on the demo person's phones in a ward with
nobody else, a draft that passes the compliance gate and one that fails it."""

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Campaign,
    CampaignMember,
    CampaignMessage,
    ConsentChannel,
    Supporter,
    SupportLevel,
    UserRole,
)
from backend.services.consent import WORDING
from backend.services.errors import Refused
from backend.services.sms import require_phone
from backend.services.targets import wards_in_area

NAMED = "Test from the campaign CRM: town hall on Saturday at 2pm. {name}"
UNNAMED = "Test from the campaign CRM: town hall on Saturday at 2pm."


@dataclass
class DemoTexting:
    campaign: str
    ward: str
    phones: list[str]
    candidate: str


async def seed_demo_texting(session: AsyncSession, phones: list[str]) -> DemoTexting:
    """Add the demo contacts and drafts to the installation's campaign; re-running replaces
    them. Commits."""
    numbers = list(dict.fromkeys(require_phone(p) for p in phones))
    campaign = await session.scalar(
        select(Campaign).options(selectinload(Campaign.candidate)).order_by(Campaign.created_at)
    )
    if campaign is None:
        raise Refused("No campaign yet. Run campaign-crm demo first.")
    name = campaign.candidate_label
    if not name:
        raise Refused("The campaign has no candidate, so no text can carry a name.")

    await session.execute(
        delete(CampaignMessage).where(
            CampaignMessage.campaign_id == campaign.id,
            CampaignMessage.status == "draft",
            CampaignMessage.body.in_([NAMED.format(name=name), UNNAMED]),
        )
    )
    await session.execute(
        delete(Supporter).where(
            Supporter.campaign_id == campaign.id, Supporter.full_name.like("Demo contact %")
        )
    )
    clash = await session.scalar(
        select(Supporter.full_name).where(
            Supporter.campaign_id == campaign.id, Supporter.phone.in_(numbers)
        )
    )
    if clash is not None:
        raise Refused(f"That number is already a contact ({clash}); use another phone.")
    taken = set(
        await session.scalars(
            select(Supporter.ward_id)
            .where(Supporter.campaign_id == campaign.id)
            .group_by(Supporter.ward_id)
            .having(func.count() > 0)
        )
    )
    ward = next((w for w in await wards_in_area(session, campaign) if w.id not in taken), None)
    if ward is None:
        raise Refused("Every ward of the seat has contacts; the demo needs one with nobody.")

    session.add_all(
        Supporter(
            campaign_id=campaign.id,
            ward_id=ward.id,
            full_name=f"Demo contact {n}",
            phone=number,
            support_level=SupportLevel.SUPPORTER,
            consent_given=True,
            consent_channel=ConsentChannel.CAMPAIGN_LINK,
            consent_wording=WORDING[ConsentChannel.CAMPAIGN_LINK],
        )
        for n, number in enumerate(numbers, start=1)
    )
    drafter = await session.scalar(
        select(CampaignMember.user_id).where(
            CampaignMember.campaign_id == campaign.id, CampaignMember.role == UserRole.MANAGER
        )
    )
    session.add_all(
        CampaignMessage(
            campaign_id=campaign.id, body=body, wards=[str(ward.id)], drafted_by_id=drafter
        )
        for body in (UNNAMED, NAMED.format(name=name))
    )
    await session.commit()
    return DemoTexting(campaign=campaign.title, ward=ward.name, phones=numbers, candidate=name)
