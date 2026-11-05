"""Walk a nominee's workspace through every aspirant status: the team's reads and writes, the
public sign-up link and the candidate page's volunteer form are open exactly while the aspirant
is approved, and a campaign with no aspirant is always open.

docs/Product_Design.md, Revision R1, decision 23 and rubric point 3.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AspirantStatus, CandidateProfile
from tests.conftest import World
from tests.test_candidates import _aspirant
from tests.test_join_api import _event

pytestmark = pytest.mark.party_only

# Every role reads the campaign list; the manager and mobilizers write supporters.
READERS = ("candidate", "manager", "mobilizer")
WRITERS = ("manager", "mobilizer")
OPEN = {"read": 200, "write": 400, "signup": True, "volunteering": True}
CLOSED = {"read": 403, "write": 403, "signup": False, "volunteering": False}


async def _answers(client: httpx.AsyncClient, world: World, link: str, profile: str) -> dict:
    reads = {
        (await client.get("/api/campaigns/", headers=world.headers(role))).status_code
        for role in READERS
    }
    writes = {
        (await client.post("/api/supporters/", headers=world.headers(role), json={})).status_code
        for role in WRITERS
    }
    page = await client.get(profile)
    return {
        "read": reads.pop() if len(reads) == 1 else reads,
        "write": writes.pop() if len(writes) == 1 else writes,
        "signup": (await client.get(link)).json()["open"],
        "volunteering": page.status_code == 200 and page.json()["volunteering_open"],
    }


@pytest.mark.parametrize("status", [None, *AspirantStatus])
async def test_a_workspace_is_open_exactly_while_its_aspirant_is_approved(
    client: httpx.AsyncClient, session: AsyncSession, world: World, status: AspirantStatus | None
) -> None:
    link = f"/api/join/{(await _event(session, world)).signup_code}/"
    aspirant = await _aspirant(session, world)
    session.add(
        CandidateProfile(campaign_id=aspirant.campaign_id, aspirant_id=aspirant.id, published=True)
    )
    await session.commit()
    (card,) = (await client.get("/api/candidates/")).json()
    profile = f"/api/candidates/{card['slug']}/"

    if status is None:
        await session.delete(aspirant)
    else:
        aspirant.status = status
    await session.commit()
    seen = await _answers(client, world, link, profile)

    if status is None:
        wanted = {**OPEN, "volunteering": False}
    else:
        wanted = OPEN if status is AspirantStatus.APPROVED else CLOSED
    assert seen == wanted
