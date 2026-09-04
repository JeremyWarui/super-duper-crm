"""Object builders, so each test only spells out what it cares about."""

from backend.models import (
    Campaign,
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


async def make_campaign(session, ward: Ward, *, office_level=OfficeLevel.WARD) -> Campaign:
    candidate = User(username=f"candidate-{ward.code}", first_name="Asha", last_name="Mwangi")
    campaign = Campaign(
        candidate=candidate,
        title=f"{ward.name} MCA 2027",
        office_level=office_level,
        ward=ward,
    )
    session.add(campaign)
    await session.commit()
    return campaign


async def make_mobilizer(session, campaign: Campaign, ward: Ward) -> Mobilizer:
    mobilizer = Mobilizer(
        campaign=campaign, ward=ward, full_name="Juma Otieno", phone="+254700000000"
    )
    session.add(mobilizer)
    await session.commit()
    return mobilizer


async def make_user(
    session,
    *,
    username: str = "manager",
    role: UserRole = UserRole.MANAGER,
    password: str = "correct-horse-battery",
    **fields,
) -> User:
    """A user who can sign in, with the password already hashed."""
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


async def sign_in(client, username: str, password: str = "correct-horse-battery") -> str:
    """The token for a user, ready to put in an Authorization header."""
    response = await client.post(
        "/api/auth/login/", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Token {token}"}


async def make_mobilizer_user(
    session,
    campaign: Campaign,
    ward: Ward,
    *,
    username: str = "juma",
    password: str = "correct-horse-battery",
) -> tuple[User, Mobilizer]:
    """A mobilizer who can sign in, and the profile that scopes them to one ward."""
    user = await make_user(
        session,
        username=username,
        role=UserRole.MOBILIZER,
        password=password,
        first_name="Juma",
        last_name="Otieno",
    )
    mobilizer = Mobilizer(campaign=campaign, ward=ward, full_name="Juma Otieno", user=user)
    session.add(mobilizer)
    await session.commit()
    return user, mobilizer
