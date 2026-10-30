"""The audit trail: written in the caller's transaction, read by a superuser only."""

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditEvent
from backend.services.audit import record
from tests.conftest import World


async def test_an_action_that_rolls_back_leaves_no_audit_row(session: AsyncSession) -> None:
    record(session, actor=None, action="campaign.create", subject_type="campaign")
    await session.rollback()

    assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_only_a_superuser_reads_the_audit_trail(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    admin_headers: dict[str, str],
) -> None:
    record(session, actor=None, action="campaign.create", subject_type="campaign")
    await session.commit()

    refused = await client.get("/api/admin/audit/", headers=world.headers("manager"))
    read = await client.get("/api/admin/audit/", headers=admin_headers)

    assert refused.status_code == 403
    assert [(e["action"], e["actor_name"]) for e in read.json()] == [("campaign.create", "cli")]
