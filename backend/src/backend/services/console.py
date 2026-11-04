"""The party console's top bar: search over the registers and the counts that need someone."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Aspirant,
    AspirantStatus,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    User,
)
from backend.schemas.console import Notification, SearchHit

HITS_SHOWN = 8


def offices(user: User) -> set[PartyRoleName]:
    """Offices a login acts in: every one for the superuser, none unless its member is approved."""
    if user.is_superuser:
        return set(PartyRoleName)
    member = user.party_member
    if member is None or member.status is not PartyMemberStatus.APPROVED:
        return set()
    return {held.role for held in user.party_roles}


def _place(aspirant: Aspirant) -> str:
    place = aspirant.ward or aspirant.constituency or aspirant.county
    return place.name if place else ""


async def search(session: AsyncSession, user: User, q: str) -> list[SearchHit]:
    """Members for the membership officer, aspirants for the nominations officer; name or phone."""
    held = offices(user)
    needle = f"%{q.strip().lower()}%"
    hits: list[SearchHit] = []
    if PartyRoleName.MEMBERSHIP_OFFICER in held:
        members = await session.scalars(
            select(PartyMember)
            .where(
                or_(func.lower(PartyMember.full_name).like(needle), PartyMember.phone.like(needle))
            )
            .order_by(PartyMember.full_name)
            .limit(HITS_SHOWN)
        )
        hits += [
            SearchHit(
                kind="member", id=m.id, label=m.full_name, detail=f"{m.status.label} · {m.phone}"
            )
            for m in members
        ]
    if PartyRoleName.NOMINATIONS_OFFICER in held:
        aspirants = await session.scalars(
            select(Aspirant)
            .join(PartyMember, PartyMember.id == Aspirant.member_id)
            .where(
                or_(func.lower(PartyMember.full_name).like(needle), PartyMember.phone.like(needle))
            )
            .options(
                selectinload(Aspirant.member),
                selectinload(Aspirant.ward),
                selectinload(Aspirant.constituency),
                selectinload(Aspirant.county),
            )
            .order_by(PartyMember.full_name)
            .limit(HITS_SHOWN)
        )
        hits += [
            SearchHit(
                kind="aspirant",
                id=a.id,
                label=a.member.full_name,
                detail=" · ".join(p for p in (a.seat.label, _place(a), a.status.label) if p),
            )
            for a in aspirants
        ]
    return hits


async def _count(session: AsyncSession, model: type, *where) -> int:
    return await session.scalar(select(func.count()).select_from(model).where(*where)) or 0


async def notifications(session: AsyncSession, user: User) -> list[Notification]:
    """What waits on each office the caller holds, with how many."""
    held = offices(user)
    found: list[Notification] = []
    if PartyRoleName.MEMBERSHIP_OFFICER in held:
        found.append(
            Notification(
                key="pending_members",
                count=await _count(
                    session, PartyMember, PartyMember.status == PartyMemberStatus.PENDING
                ),
            )
        )
    if PartyRoleName.NOMINATIONS_OFFICER in held:
        found.append(
            Notification(
                key="submitted_aspirants",
                count=await _count(session, Aspirant, Aspirant.status == AspirantStatus.SUBMITTED),
            )
        )
    return found
