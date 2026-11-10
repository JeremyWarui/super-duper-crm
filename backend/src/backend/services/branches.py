"""County branches: published ones for the public site, every county's for the party office."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_or_refuse, replace_fields
from backend.models import Branch, Constituency, County, User
from backend.schemas.content import BranchUpdate
from backend.services.audit import record
from backend.services.branch_officials import current_by_branch, public
from backend.services.errors import NotFound


def _read(branch: Branch, officials: dict, *, admin: bool = False) -> dict:
    """A branch with its officials in office; the party office also sees whether it is public."""
    read = {
        **{c: getattr(branch, c) for c in BRANCH_FIELDS},
        "county": branch.county,
        "officials": public(officials.get(branch.id, [])),
    }
    if admin:
        read |= {"published": branch.published, "updated_at": branch.updated_at}
    return read


async def published(session: AsyncSession, today: date) -> list[dict]:
    rows = list(
        await session.scalars(
            select(Branch)
            .join(Branch.county)
            .where(Branch.published.is_(True))
            .options(selectinload(Branch.county))
            .order_by(County.name)
        )
    )
    officials = await current_by_branch(session, [b.id for b in rows], today)
    return [_read(b, officials) for b in rows]


async def published_detail(session: AsyncSession, county_id: uuid.UUID, today: date) -> dict:
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
    officials = await current_by_branch(session, [branch.id], today)
    return {
        **_read(branch, officials),
        "constituencies": [
            {"id": k.id, "name": k.name, "wards": sorted(k.wards, key=lambda w: w.name)}
            for k in constituencies
        ],
    }


BRANCH_FIELDS = (
    "office_address",
    "phone",
    "email",
    "next_meeting_on",
    "next_meeting_venue",
)


async def by_county(session: AsyncSession, today: date) -> list[dict]:
    """Every county with its branch, or None, by county name."""
    counties = list(await session.scalars(select(County).order_by(County.name)))
    branches = {
        b.county_id: b
        for b in await session.scalars(select(Branch).options(selectinload(Branch.county)))
    }
    officials = await current_by_branch(session, [b.id for b in branches.values()], today)
    return [
        {
            "county": c,
            "branch": _read(branches[c.id], officials, admin=True) if c.id in branches else None,
        }
        for c in counties
    ]


async def save(
    session: AsyncSession, county_id: uuid.UUID, payload: BranchUpdate, *, actor: User, today: date
) -> dict:
    """Write the county's branch, creating it on first save, and audit the changed fields."""
    await get_or_refuse(session, County, county_id, "county")
    branch = await session.scalar(select(Branch).where(Branch.county_id == county_id))
    if branch is None:
        branch = Branch(county_id=county_id)
        session.add(branch)
    changed = replace_fields(branch, payload.model_dump())
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
    saved = await session.scalar(
        select(Branch).where(Branch.id == branch.id).options(selectinload(Branch.county))
    )
    return _read(saved, await current_by_branch(session, [saved.id], today), admin=True)
