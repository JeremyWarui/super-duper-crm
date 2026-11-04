"""Walk a member login through every member status: it signs in only while approved, and an
open session ends at the next request once the member stops being approved.

docs/Volunteers_Design.md, rubric points 4 and 5.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import PartyMemberStatus
from tests.conftest import World
from tests.factories import TEST_PASSWORD, auth, fresh_password
from tests.test_account_api import APPLICANT, LOGIN, _joined


@pytest.mark.parametrize("status", list(PartyMemberStatus))
async def test_a_member_login_works_only_while_its_member_is_approved(
    client: httpx.AsyncClient, session: AsyncSession, world: World, status: PartyMemberStatus
) -> None:
    member = await _joined(client, session, world)
    member.status = PartyMemberStatus.APPROVED
    await session.commit()
    token = (
        await client.post(LOGIN, json={"email": APPLICANT, "password": TEST_PASSWORD})
    ).json()["token"]
    wrong = await client.post(LOGIN, json={"email": APPLICANT, "password": fresh_password()})

    member.status = status
    await session.commit()
    open_session = await client.get("/api/account/", headers=auth(token))
    signing_in = await client.post(LOGIN, json={"email": APPLICANT, "password": TEST_PASSWORD})

    if status is PartyMemberStatus.APPROVED:
        assert (open_session.status_code, signing_in.status_code) == (200, 200)
    else:
        assert open_session.status_code == 401
        assert (signing_in.status_code, signing_in.json()) == (wrong.status_code, wrong.json())
