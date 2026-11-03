"""Object builders, so each test spells out only what it cares about."""

import secrets
import uuid
import zlib
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update

from backend.models import (
    Campaign,
    CampaignMember,
    CampaignSubscription,
    Constituency,
    County,
    Mobilizer,
    OfficeLevel,
    PartyConsentChannel,
    PartyMember,
    PartyMemberStatus,
    PartyRole,
    PartyRoleName,
    RegistrationCentre,
    User,
    UserRole,
    Ward,
)
from backend.security import hash_password
from backend.services.accounts import add_member
from backend.services.consent import PARTY_WORDING

# The date every API test runs on; test campaigns are paid a year past it.
TEST_TODAY = date(2026, 11, 1)
PAID_UNTIL = TEST_TODAY + timedelta(days=365)


def paid(campaign: Campaign) -> Campaign:
    """The campaign, its subscription paid until a year after the test date."""
    campaign.subscription.paid_until = PAID_UNTIL
    return campaign


async def pay(session, campaign_id: uuid.UUID | str) -> None:
    """Pay a campaign made through the API until a year after the test date."""
    await session.execute(
        update(CampaignSubscription)
        .where(CampaignSubscription.campaign_id == uuid.UUID(str(campaign_id)))
        .values(paid_until=PAID_UNTIL)
    )
    await session.commit()


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
    role: UserRole | None = UserRole.MANAGER,
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
        email=fields.pop("email", email_of(username)),
        **fields,
    )
    session.add(user)
    await session.commit()
    return user


async def make_officer(session, ward: Ward, *roles: PartyRoleName, username: str = "ofisa") -> User:
    """A staff login holding `roles`, linked to its own approved party member."""
    member = PartyMember(
        full_name=f"Officer {username}",
        phone=f"+2547{zlib.crc32(username.encode()) % 100_000_000:08d}",
        ward_id=ward.id,
        status=PartyMemberStatus.APPROVED,
        consent_wording=PARTY_WORDING[PartyConsentChannel.OFFICER_ENTRY],
        consent_channel=PartyConsentChannel.OFFICER_ENTRY,
        consent_at=datetime.now(UTC),
    )
    session.add(member)
    await session.flush()
    officer = await make_user(session, username=username, role=None, party_member_id=member.id)
    session.add_all(PartyRole(user_id=officer.id, role=role) for role in roles)
    await session.commit()
    return officer


async def make_campaign(session, ward: Ward, *, office_level=OfficeLevel.WARD) -> Campaign:
    """A ward campaign with its own candidate."""
    candidate = await make_user(
        session,
        username=f"candidate-{ward.code}",
        role=UserRole.CANDIDATE,
        first_name="Asha",
        last_name="Mwangi",
    )
    campaign = paid(Campaign(title=f"{ward.name} MCA 2027", office_level=office_level, ward=ward))
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
    campaign = paid(Campaign(title=title, office_level=OfficeLevel.WARD, ward_id=ward.id))
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


def email_of(username: str) -> str:
    """The email a test login signs in with."""
    return f"{username.lower()}@example.test"


async def sign_in(client, username: str, password: str = TEST_PASSWORD) -> str:
    """A token for the login, signing in with `username`'s test email or an email given."""
    email = username if "@" in username else email_of(username)
    response = await client.post("/api/auth/login/", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Token {token}"}


def join_details(centre, **overrides) -> dict:
    """The keyword arguments of `membership.request_join` for an applicant at `centre`."""
    return {
        "first_name": "Achieng",
        "surname": "Otieno",
        "phone": "+254711222333",
        "email": "achieng@example.com",
        "password_hash": "$argon2id$test",
        "ward_id": centre.ward_id,
        "registration_centre_id": centre.id,
        **overrides,
    }
