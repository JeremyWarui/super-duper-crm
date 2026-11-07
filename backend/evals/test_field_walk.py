"""Walk a mobilizer and an agent from the public team link to their own paid payment, in every
workspace kind, through the HTTP API.

docs/Product_Design.md, section 0.5, the PD-16 acceptance line.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.db.session import get_session, get_session_factory
from backend.main import app
from backend.models import (
    Agent,
    OrganisationType,
    RegistrationCentre,
    User,
    UserRole,
    Ward,
    WorkspaceKind,
)
from backend.security import hash_password
from backend.services.accounts import add_member
from backend.services.email import PracticeEmailProvider
from backend.services.targets import generate_targets
from tests.conftest import World, app_client
from tests.factories import auth, claim_link, fresh_password, make_campaign, make_user, sign_in
from tests.test_candidates import _aspirant
from tests.test_party_workspace import _coordinator, _workspace

KINDS = pytest.mark.parametrize(
    ("kind", "organisation_type"),
    [
        ("standalone", OrganisationType.ASPIRANT),
        ("standalone-mca", OrganisationType.ASPIRANT),
        ("hosted", OrganisationType.PARTY),
        ("party", OrganisationType.PARTY),
    ],
    ids=["standalone", "standalone-mca", "hosted", "party"],
    indirect=["organisation_type"],
)
ROLES = pytest.mark.parametrize("role", ["mobilizer", "agent"])
AMOUNT = 1500
NAME = "Achieng Otieno"
EMAIL = "achieng@example.test"
PHONE = "+254712345001"


@dataclass
class Team:
    """Who runs the walk in a workspace: `lead` decides, assigns and schedules; `approver` pays,
    and is refused scheduling with `scheduling_refused`."""

    campaign: str
    lead: dict[str, str]
    approver: dict[str, str]
    approver_role: str
    scheduling_refused: int


@pytest.fixture
async def client(
    engine: AsyncEngine, session: AsyncSession, organisation_type: OrganisationType
) -> AsyncIterator[httpx.AsyncClient]:
    """The app with a new session per request and production's session settings, so no request
    leans on objects an earlier one loaded."""
    fresh = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def per_request() -> AsyncIterator[AsyncSession]:
        async with fresh() as opened:
            yield opened

    async with app_client(session, organisation_type) as http_client:
        app.dependency_overrides[get_session] = per_request
        app.dependency_overrides[get_session_factory] = lambda: fresh
        yield http_client


async def _team(
    kind: str,
    session: AsyncSession,
    client: httpx.AsyncClient,
    world: World,
    admin_headers: dict[str, str],
    ward: Ward,
) -> Team:
    """The workspace of this kind and its people; a party coordinator's area is `ward`."""
    if kind == "party":
        campaign, _ = await _workspace(session, client, admin_headers)
        return Team(
            str(campaign.id),
            lead=await _coordinator(session, client, campaign, ward, "otieno"),
            approver=auth(await sign_in(client, "wm@example.com")),
            approver_role="manager",
            scheduling_refused=400,
        )
    if kind == "standalone-mca":
        campaign = await make_campaign(session, world.ward)
        campaign.kind = WorkspaceKind.STANDALONE
        await add_member(session, campaign.id, await make_user(session, username="mca-manager"))
        await generate_targets(session, campaign)
        await session.commit()
        return Team(
            str(campaign.id),
            lead=auth(await sign_in(client, "mca-manager")),
            approver=auth(await sign_in(client, f"candidate-{world.ward.code}")),
            approver_role="candidate",
            scheduling_refused=403,
        )
    if kind == "hosted":
        await _aspirant(session, world)
    else:
        world.campaign.kind = WorkspaceKind.STANDALONE
        await session.commit()
    return Team(
        str(world.campaign.id),
        lead=world.headers("manager"),
        approver=world.headers("candidate"),
        approver_role="candidate",
        scheduling_refused=403,
    )


async def _cannot_sign_in_while_pending(
    client: httpx.AsyncClient, session: AsyncSession, email: str
) -> str:
    """Refused with the right password, and no reset link; returns that password, which the test
    sets because a sign-up's is random."""
    known = fresh_password()
    login = await session.scalar(select(User).where(User.email == email))
    login.password_hash = hash_password(known)
    await session.commit()

    tried = await client.post("/api/auth/login/", json={"email": email, "password": known})
    reset = await client.post("/api/auth/password-reset/", json={"email": email})

    assert tried.status_code == 400, tried.text
    assert reset.is_success, reset.text
    assert [to for to, _, _ in PracticeEmailProvider.outbox if to == email] == []
    return known


async def _someone_elses_payment(
    session: AsyncSession, client: httpx.AsyncClient, team: Team, ward: Ward
) -> None:
    """Another agent on the workspace, with a scheduled payment for done work in `ward`."""
    other = await make_user(session, username="wairimu", role=UserRole.AGENT, phone="+254712345999")
    await add_member(session, uuid.UUID(team.campaign), other)
    agent = Agent(campaign_id=uuid.UUID(team.campaign), user_id=other.id, ward_id=ward.id)
    session.add(agent)
    await session.commit()
    work = await client.post(
        "/api/assignments/",
        headers=team.lead,
        json={
            "campaign": team.campaign,
            "agent": str(agent.id),
            "kind": "activity",
            "description": "Someone else's work",
            "amount_kes": AMOUNT + 1,
        },
    )
    assert work.status_code == 201, work.text
    await client.post(f"/api/assignments/{work.json()['id']}/done/", headers=team.lead)
    made = await client.post(
        "/api/payments/", headers=team.lead, json={"assignment": work.json()["id"]}
    )
    assert made.status_code == 201, made.text


@KINDS
@ROLES
async def test_a_person_signs_up_and_sees_their_own_payment_paid_through_the_routing(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict[str, str],
    kind: str,
    role: str,
) -> None:
    session.add(
        RegistrationCentre(
            ward_id=world.ward.id, name="Zimmerman Secondary", code="002", registered_voters=900
        )
    )
    await session.commit()
    # Juma holds Zimmerman on the world's campaign, so a mobilizer there takes the next ward.
    takes_next = role == "mobilizer" and kind != "standalone-mca"
    ward = world.other_ward if takes_next else world.ward
    team = await _team(kind, session, client, world, admin_headers, ward)
    in_campaign = f"?campaign={team.campaign}"
    coverage_url = f"/api/agents/coverage/{in_campaign}"
    queue = f"/api/campaigns/{team.campaign}/registrations/"

    # The public link offers the seat's places.
    code = (
        await client.get(f"/api/campaigns/{team.campaign}/team-link/", headers=team.lead)
    ).json()
    link = f"/api/team-signup/{code['code']}/"
    page = (await client.get(link)).json()
    assert page["open"] is True
    assert ward.name in {w["name"] for w in page["wards"]}
    assert page["mobilizer_place"] == ("centre" if kind == "standalone-mca" else "ward")
    place = {"ward": str(ward.id)}
    if role == "agent" or page["mobilizer_place"] == "centre":
        centres = (await client.get(f"{link}centres/?ward={ward.id}")).json()
        assert [c["name"] for c in centres] == ["Zimmerman Primary", "Zimmerman Secondary"]
        place = {"registration_centre": centres[0]["id"]}

    # Sign-up leaves a pending login.
    signed_up = await client.post(
        link,
        json={
            "role": role,
            "first_name": "Achieng",
            "last_name": "Otieno",
            "phone": "0712 345001",
            "email": EMAIL,
            "id_number": "12345678",
            "consent_given": True,
            **place,
        },
    )
    assert signed_up.status_code == 201, signed_up.text
    known = await _cannot_sign_in_while_pending(client, session, EMAIL)

    # Agent coverage before approval.
    before = (await client.get(coverage_url, headers=team.approver)).json()
    assert (before["centres"], before["covered"]) == (2, 0)

    # Approval emails the invite, which signs them in.
    (row,) = (await client.get(f"{queue}?status=pending", headers=team.lead)).json()
    assert (row["role"], row["full_name"], row["phone"]) == (role, NAME, PHONE)
    approved = await client.post(f"{queue}{row['id']}/approve/", headers=team.lead)
    assert approved.status_code == 200, approved.text
    assert (approved.json()["invite"], approved.json()["placed"]) == ("email", True)
    # The password refused while pending opens now, so the refusal was the pending state's.
    opened = await client.post("/api/auth/login/", json={"email": EMAIL, "password": known})
    assert opened.status_code == 200, opened.text
    chosen = fresh_password()
    await claim_link(client, session, EMAIL, chosen)
    person = auth(await sign_in(client, EMAIL, chosen))

    # Coverage counts the centre for an agent, and nothing for a mobilizer.
    after = (await client.get(coverage_url, headers=team.approver)).json()
    if role == "agent":
        assert (after["centres"], after["covered"]) == (2, 1)
        assert [c["name"] for c in after["uncovered"]] == ["Zimmerman Secondary"]
    else:
        assert after == before

    # The lead assigns them work at their own place, beside someone else's payment.
    await _someone_elses_payment(session, client, team, ward)
    roster = (await client.get(f"/api/{role}s/{in_campaign}", headers=team.lead)).json()
    (member,) = [m for m in roster if m["full_name"] == NAME]
    assigned = await client.post(
        "/api/assignments/",
        headers=team.lead,
        json={
            "campaign": team.campaign,
            role: member["id"],
            "kind": "activity",
            "description": "Door to door",
            "amount_kes": AMOUNT,
        },
    )
    assert assigned.status_code == 201, assigned.text
    work = assigned.json()
    assert (work["member_name"], work["member_role"], work["ward_name"]) == (NAME, role, ward.name)
    own_work = (await client.get(f"/api/assignments/{in_campaign}", headers=person)).json()
    assert [(a["id"], a["status"]) for a in own_work] == [(work["id"], "assigned")]

    # Marked done, it can be scheduled, by the lead and not the approver.
    done = await client.post(f"/api/assignments/{work['id']}/done/", headers=team.lead)
    assert done.json()["status"] == "done", done.text
    pay = {"assignment": work["id"]}
    barred = await client.post("/api/payments/", headers=team.approver, json=pay)
    assert barred.status_code == team.scheduling_refused, barred.text
    scheduled = await client.post("/api/payments/", headers=team.lead, json=pay)
    assert scheduled.status_code == 201, scheduled.text
    payment = scheduled.json()
    assert payment["approver_role"] == team.approver_role
    assert (payment["recipient_name"], payment["recipient_phone"]) == (NAME, PHONE)
    assert (payment["amount_kes"], payment["status"]) == (AMOUNT, "scheduled")

    # Only the routed approver releases it, and practice mode moves no money.
    mode = (await client.get("/api/payments/payout-mode/", headers=team.approver)).json()
    assert mode == {"mode": "practice", "moves_money": False}
    release = f"/api/payments/{payment['id']}/release/"
    assert (await client.post(release, headers=team.lead)).status_code == 403
    released = await client.post(release, headers=team.approver)
    assert released.status_code == 200, released.text

    # They see their own payment paid, and nobody else's.
    (own,) = (await client.get(f"/api/payments/{in_campaign}", headers=person)).json()
    assert (own["id"], own[role]) == (payment["id"], member["id"])
    assert (own["status"], own["amount_kes"], own["provider"]) == ("paid", AMOUNT, "practice")
    assert own["reference"].startswith("PRACTICE")
    assert own["paid_at"] is not None
    own_work = (await client.get(f"/api/assignments/{in_campaign}", headers=person)).json()
    assert [a["status"] for a in own_work] == ["done"]
