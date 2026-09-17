"""Object builders, so each test spells out only what it cares about."""

import secrets
import uuid

from sqlalchemy import select

from backend.models import (
    Campaign,
    CampaignMember,
    Constituency,
    County,
    Mobilizer,
    OfficeLevel,
    RegistrationCentre,
    User,
    UserRole,
    Ward,
)
from backend.security import hash_password
from backend.services.accounts import add_member

# Generated per run, so no literal reads as a credential.
TEST_PASSWORD = secrets.token_urlsafe(16)


def fresh_password() -> str:
    """A random password that never starts with "-", which argparse would read as a flag."""
    return "p" + secrets.token_urlsafe(16)


async def make_geography(session, *, ward_voters: int | None = 10_000):
    """County -> Constituency -> Ward -> RegistrationCentre, committed."""
    county = County(name="Nairobi", code="047", registered_voters=2_400_000)
    constituency = Constituency(county=county, name="Westlands", code="274")
    ward = Ward(
        constituency=constituency, name="Parklands", code="1370", registered_voters=ward_voters
    )
    centre = RegistrationCentre(
        ward=ward, name="Parklands Primary", code="001", registered_voters=2_000
    )
    session.add(county)
    await session.commit()
    return county, constituency, ward, centre


async def make_user(
    session,
    *,
    username: str = "manager",
    role: UserRole = UserRole.MANAGER,
    password: str = TEST_PASSWORD,
    **fields,
) -> User:
    """A login that can sign in."""
    user = User(
        username=username,
        role=role,
        password_hash=hash_password(password),
        first_name=fields.pop("first_name", "Amina"),
        last_name=fields.pop("last_name", "Kariuki"),
        **fields,
    )
    session.add(user)
    await session.commit()
    return user


async def make_campaign(session, ward: Ward, *, office_level=OfficeLevel.WARD) -> Campaign:
    """A ward campaign with its own candidate."""
    candidate = await make_user(
        session,
        username=f"candidate-{ward.code}",
        role=UserRole.CANDIDATE,
        first_name="Asha",
        last_name="Mwangi",
    )
    campaign = Campaign(title=f"{ward.name} MCA 2027", office_level=office_level, ward=ward)
    session.add(campaign)
    await session.flush()
    await add_member(session, campaign.id, candidate)
    await session.commit()
    return campaign


async def make_rival_campaign(
    session, ward: Ward, *, title: str = "Rival for Githurai", owner: str = "rival"
) -> Campaign:
    """A ward campaign that belongs to somebody else."""
    rival = await make_user(session, username=owner, role=UserRole.CANDIDATE)
    campaign = Campaign(title=title, office_level=OfficeLevel.WARD, ward_id=ward.id)
    session.add(campaign)
    await session.flush()
    await add_member(session, campaign.id, rival)
    await session.commit()
    return campaign


async def make_mobilizer(session, campaign: Campaign, ward: Ward) -> Mobilizer:
    """A ground row with no login."""
    mobilizer = Mobilizer(
        campaign=campaign, ward=ward, full_name="Juma Otieno", phone="+254700000000"
    )
    session.add(mobilizer)
    await session.commit()
    return mobilizer


async def make_mobilizer_user(
    session,
    campaign: Campaign,
    ward: Ward,
    *,
    username: str = "juma",
    password: str = TEST_PASSWORD,
) -> tuple[User, Mobilizer]:
    """A mobilizer login on the campaign, and its ground row."""
    user = await make_user(
        session,
        username=username,
        role=UserRole.MOBILIZER,
        password=password,
        first_name="Juma",
        last_name="Otieno",
    )
    await add_member(session, campaign.id, user)
    mobilizer = Mobilizer(campaign=campaign, ward=ward, full_name="Juma Otieno", user=user)
    session.add(mobilizer)
    await session.commit()
    return user, mobilizer


async def members_of(session, campaign_id: uuid.UUID) -> dict[str, str]:
    """username -> role on that campaign."""
    rows = await session.execute(
        select(User.username, CampaignMember.role)
        .join(CampaignMember, CampaignMember.user_id == User.id)
        .where(CampaignMember.campaign_id == campaign_id)
    )
    return {username: role.value for username, role in rows}


async def sign_in(client, username: str, password: str = TEST_PASSWORD) -> str:
    """A token for the login."""
    response = await client.post(
        "/api/auth/login/", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Token {token}"}
