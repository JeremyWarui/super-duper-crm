"""Request dependencies: the session, the signed-in caller, and role guards."""

from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.session import get_session
from backend.models import (
    AccessState,
    Aspirant,
    AspirantStatus,
    AuthToken,
    CampaignMember,
    CampaignSubscription,
    PartyMember,
    PartyMemberStatus,
    PartyRoleName,
    PartySettings,
    User,
    UserKind,
    UserRole,
)
from backend.services import billing, membership
from backend.services.errors import CampaignClosed

SessionDep = Annotated[AsyncSession, Depends(get_session)]

TOKEN_SCHEME = "Token"
_header = APIKeyHeader(name="Authorization", auto_error=False, scheme_name="Token")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": TOKEN_SCHEME}
    )


async def get_signed_in_user(
    session: SessionDep, header: Annotated[str | None, Depends(_header)]
) -> User:
    """The caller named by "Authorization: Token <key>"; 401 when absent or unknown."""
    if not header:
        raise _unauthorized("Authentication credentials were not provided.")
    scheme, _, key = header.partition(" ")
    if scheme != TOKEN_SCHEME or not key.strip():
        raise _unauthorized("Invalid token.")
    token = await session.scalar(
        select(AuthToken)
        .where(AuthToken.key == key.strip())
        .options(
            selectinload(AuthToken.user).selectinload(User.mobilizer_profile),
            selectinload(AuthToken.user).selectinload(User.party_roles),
            selectinload(AuthToken.user).selectinload(User.party_member),
        )
    )
    if token is None or not token.user.is_active:
        raise _unauthorized("Invalid token.")
    return token.user


SignedInUser = Annotated[User, Depends(get_signed_in_user)]


async def get_today() -> date:
    return billing.today()


Today = Annotated[date, Depends(get_today)]

SUSPENDED = "This campaign is suspended by the party."
CLOSED = "This campaign is closed: its aspirant has withdrawn."
LOCKED = "This campaign's subscription is not active."
READ_ONLY = "This campaign is read-only until its subscription is renewed."
READS = frozenset({"GET", "HEAD", "OPTIONS"})


async def get_current_user(
    user: SignedInUser, session: SessionDep, request: Request, today: Today
) -> User:
    """The signed-in caller, refused while their campaign's aspirant is not approved or its
    subscription does not allow this request.

    A campaign with no subscription row counts as locked. A member login is refused: it opens
    only the member account.
    """
    if user.kind is UserKind.MEMBER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A member login opens only its account.")
    if user.role is None or user.is_superuser:
        return user
    row = (
        await session.execute(
            select(
                Aspirant.status,
                CampaignSubscription.id,
                CampaignSubscription.paid_until,
                CampaignSubscription.hold,
                PartySettings.grace_days,
                PartySettings.read_only_days,
            )
            .select_from(CampaignMember)
            .outerjoin(Aspirant, Aspirant.campaign_id == CampaignMember.campaign_id)
            .outerjoin(
                CampaignSubscription,
                CampaignSubscription.campaign_id == CampaignMember.campaign_id,
            )
            .outerjoin(PartySettings, PartySettings.id == 1)
            .where(CampaignMember.user_id == user.id)
        )
    ).first()
    if row is None:
        return user
    aspirant, subscription, paid_until, hold, grace_days, read_only_days = row
    if aspirant is AspirantStatus.SUSPENDED:
        raise CampaignClosed(SUSPENDED)
    if aspirant is not None and aspirant is not AspirantStatus.APPROVED:
        raise CampaignClosed(CLOSED)
    if subscription is None:
        raise CampaignClosed(LOCKED, code="campaign_locked")
    state = billing.access(
        paid_until,
        hold,
        today,
        billing.GRACE_DAYS if grace_days is None else grace_days,
        billing.READ_ONLY_DAYS if read_only_days is None else read_only_days,
    ).state
    if state in billing.NO_ACCESS:
        raise CampaignClosed(LOCKED, code="campaign_locked")
    if state is AccessState.READ_ONLY and request.method not in READS:
        raise CampaignClosed(READ_ONLY, code="campaign_read_only")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole, message: str | None = None):
    """A guard letting only these roles through; 403 otherwise."""

    async def dependency(user: CurrentUser) -> User:
        if user.role is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, message or "This login has no campaign role."
            )
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, message or f"A {user.role.label} may not change this."
            )
        return user

    return dependency


async def require_superuser(user: CurrentUser) -> User:
    if not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is not yours to see.")
    return user


def require_party_role(*roles: PartyRoleName):
    """A guard letting through a superuser, or a holder of one of these offices whose login is
    linked to an approved party member.

    Applies the party inbox first, so a queued withdrawal of the officer's own membership
    stops them on this request, not the next.
    """

    async def dependency(user: CurrentUser, session: SessionDep) -> User:
        if user.is_superuser:
            return user
        if not any(held.role in roles for held in user.party_roles):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "This needs a party office you do not hold."
            )
        await membership.process_requests(session)
        own = (
            await session.scalar(
                select(PartyMember.status).where(PartyMember.id == user.party_member_id)
            )
            if user.party_member_id
            else None
        )
        if own is not PartyMemberStatus.APPROVED:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "This login needs to be linked to an approved party member.",
            )
        return user

    return dependency


AdminUser = Annotated[User, Depends(require_superuser)]
MembershipOfficer = Annotated[User, Depends(require_party_role(PartyRoleName.MEMBERSHIP_OFFICER))]
NominationsOfficer = Annotated[User, Depends(require_party_role(PartyRoleName.NOMINATIONS_OFFICER))]
FinanceOfficer = Annotated[User, Depends(require_party_role(PartyRoleName.FINANCE_OFFICER))]
Writer = Annotated[User, Depends(require_role(UserRole.MANAGER))]
MobilizerWriter = Annotated[User, Depends(require_role(UserRole.MANAGER, UserRole.MOBILIZER))]
TeamWriter = Annotated[
    User,
    Depends(
        require_role(
            UserRole.MANAGER,
            UserRole.CANDIDATE,
            message="Only a candidate or a campaign manager may add or remove people.",
        )
    ),
]
SupporterTeam = Annotated[
    User,
    Depends(
        require_role(
            UserRole.MANAGER,
            UserRole.MOBILIZER,
            message="The supporter register is for the campaign team.",
        )
    ),
]
