"""County branches: published ones for the public site, every county's for the superuser."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Branch, Constituency, County, User
from backend.schemas.content import BranchUpdate
from backend.services.audit import record
from backend.services.errors import NotFound


async def published(session: AsyncSession) -> list[Branch]:
    return list(
        await session.scalars(
            select(Branch)
            .join(Branch.county)
            .where(Branch.published.is_(True))
            .options(selectinload(Branch.county))
            .order_by(County.name)
        )
    )


async def published_detail(session: AsyncSession, county_id: uuid.UUID) -> dict:
    """A published branch and its county's constituencies and wards, by name."""
    branch = await session.scalar(
        select(Branch)
        .where(Branch.county_id == county_id, Branch.published.is_(True))
        .options(selectinload(Branch.county))
    )
    if branch is None:
        raise NotFound("No such branch.")
    constituencies = await session.scalars(
        select(Constituency)
        .where(Constituency.county_id == county_id)
        .options(selectinload(Constituency.wards))
        .order_by(Constituency.name)
    )
    return {
        **{c: getattr(branch, c) for c in BRANCH_FIELDS},
        "county": branch.county,
        "constituencies": [
            {"id": k.id, "name": k.name, "wards": sorted(k.wards, key=lambda w: w.name)}
            for k in constituencies
        ],
    }


BRANCH_FIELDS = (
    "chairperson",
    "secretary",
    "office_address",
    "phone",
    "email",
    "next_meeting_on",
    "next_meeting_venue",
)


async def by_county(session: AsyncSession) -> list[dict]:
    """Every county with its branch, or None, by county name."""
    counties = list(await session.scalars(select(County).order_by(County.name)))
    branches = {
        b.county_id: b
        for b in await session.scalars(select(Branch).options(selectinload(Branch.county)))
    }
    return [{"county": c, "branch": branches.get(c.id)} for c in counties]


async def save(
    session: AsyncSession, county_id: uuid.UUID, payload: BranchUpdate, *, actor: User
) -> Branch:
    """Write the county's branch, creating it on first save, and audit the changed fields."""
    if await session.get(County, county_id) is None:
        raise NotFound("No such county.")
    branch = await session.scalar(select(Branch).where(Branch.county_id == county_id))
    if branch is None:
        branch = Branch(county_id=county_id)
        session.add(branch)
    values = payload.model_dump()
    changed = sorted(k for k, v in values.items() if getattr(branch, k, None) != v)
    for name, value in values.items():
        setattr(branch, name, value)
    branch.updated_at = datetime.now(UTC)
    await session.flush()
    record(
        session,
        actor=actor,
        action="party.branch.save",
        subject_type="branch",
        subject_id=branch.id,
        detail={"fields": changed, "published": branch.published},
    )
    await session.commit()
    return await session.scalar(
        select(Branch).where(Branch.id == branch.id).options(selectinload(Branch.county))
    )
