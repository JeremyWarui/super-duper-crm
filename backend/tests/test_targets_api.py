"""Reading and editing vote targets through the API."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Supporter, SupportLevel, Target
from backend.services import admin
from tests.conftest import World


async def _targets(client: httpx.AsyncClient, world: World, role: str = "manager") -> list[dict]:
    response = await client.get(
        f"/api/targets/?campaign={world.campaign.id}", headers=world.headers(role)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_every_screen_counts_the_same_supporters(
    client: httpx.AsyncClient, session: AsyncSession, world: World
) -> None:
    """Overview, Targets, the turnout preview and the console read one live count."""
    zimmerman = world.ward
    session.add_all(
        [
            Supporter(
                campaign_id=world.campaign.id,
                ward_id=zimmerman.id,
                full_name=f"S{n}",
                support_level=SupportLevel.SUPPORTER,
            )
            for n in range(3)
        ]
        + [
            Supporter(
                campaign_id=world.campaign.id,
                ward_id=zimmerman.id,
                full_name="Opposed",
                support_level=SupportLevel.OPPOSED,
            )
        ]
    )
    stale = await session.scalar(select(Target).where(Target.ward_id == zimmerman.id))
    stale.votes_committed = 999
    await session.commit()

    targets = await _targets(client, world)
    overview = (
        await client.get(
            f"/api/strategy/?campaign={world.campaign.id}", headers=world.headers("manager")
        )
    ).json()
    preview = (
        await client.get(
            f"/api/campaigns/{world.campaign.id}/targets/preview/", headers=world.headers("manager")
        )
    ).json()
    console = (await admin.campaigns(session, world.campaign.id))[0]

    on_targets = next(r["votes_committed"] for r in targets if r["ward"] == str(zimmerman.id))
    on_overview = next(u["committed"] for u in overview["units"] if u["ward"] == str(zimmerman.id))
    on_preview = next(u["supporters"] for u in preview["units"] if u["ward"] == str(zimmerman.id))
    assert on_targets == on_overview == on_preview == 3
    assert overview["committed"] == preview["supporters"] == console.votes_committed == 3
