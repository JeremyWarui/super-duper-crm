"""A party member's own account: their details, their volunteering, and leaving the party."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload, selectinload

from backend.api.deps import SessionDep, SignedInUser
from backend.models import (
    Constituency,
    PartyMember,
    User,
    UserKind,
    VolunteerStatus,
    Ward,
)
from backend.schemas.account import AccountRead, AccountVolunteer
from backend.schemas.party import VolunteerPart
from backend.security import new_withdraw_code
from backend.services import membership, volunteers
from backend.services.accounts import sign_out

router = APIRouter(prefix="/account", tags=["account"])


def masked(phone: str) -> str:
    """+254712345678 as 07•• ••• 678."""
    local = "0" + phone[4:] if phone.startswith("+254") else phone
    return f"{local[:2]}•• ••• {local[-3:]}"


async def _member(session: SessionDep, user: User) -> PartyMember | None:
    return await session.scalar(
        select(PartyMember)
        .where(PartyMember.id == user.party_member_id)
        .options(
            joinedload(PartyMember.ward)
            .joinedload(Ward.constituency)
            .joinedload(Constituency.county),
            joinedload(PartyMember.registration_centre),
            selectinload(PartyMember.volunteer),
        )
        .execution_options(populate_existing=True)
    )


async def get_account_member(user: SignedInUser, session: SessionDep) -> PartyMember:
    """The approved member this login opens.

    Applies the party inbox first, so a queued withdrawal ends the session on this request.
    A member login whose member is no longer approved gets 401; any other login without an
    approved member gets 403.
    """
    if user.party_member_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This login has no member account.")
    await membership.process_requests(session)
    member = await _member(session, user)
    if member is None or not member.is_approved:
        if user.kind is UserKind.MEMBER:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your membership is not active.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This login has no member account.")
    return member


AccountMember = Annotated[PartyMember, Depends(get_account_member)]


def _read(member: PartyMember) -> AccountRead:
    profile = member.volunteer
    volunteer = None
    if profile is not None and profile.status is not VolunteerStatus.WITHDRAWN:
        volunteer = AccountVolunteer(
            status=profile.status,
            profession=profile.profession,
            profession_other=profile.profession_other,
            areas=profile.interests,
            area_other=profile.interest_other,
            preferred_contact=profile.preferred_contact,
            consent_wording=profile.consent_wording,
            consent_at=profile.consent_at,
        )
    return AccountRead(
        first_name=member.first_name or member.full_name.split(" ")[0],
        full_name=member.full_name,
        phone=masked(member.phone),
        email=member.email,
        status=member.status,
        **member.places,
        registration_centre=member.registration_centre,
        member_since=member.created_at,
        consent_wording=member.consent_wording,
        consent_at=member.consent_at,
        volunteer=volunteer,
    )


@router.get("/", response_model=AccountRead)
async def read_account(member: AccountMember) -> AccountRead:
    """The member card, details, consents and volunteer profile."""
    return _read(member)


@router.put("/volunteer/", response_model=AccountRead)
async def change_volunteering(
    payload: VolunteerPart, member: AccountMember, user: SignedInUser, session: SessionDep
) -> AccountRead:
    """Change the volunteer details, or volunteer when not volunteering."""
    await volunteers.own_update(session, member, payload.model_dump(), actor=user)
    await session.commit()
    return _read(await _member(session, user))


@router.post("/volunteer/stop/", response_model=AccountRead)
async def stop_volunteering(
    member: AccountMember, user: SignedInUser, session: SessionDep
) -> AccountRead:
    """Stop volunteering and stay a member."""
    await volunteers.own_stop(session, member, actor=user)
    await session.commit()
    return _read(await _member(session, user))


@router.post("/leave/", status_code=status.HTTP_204_NO_CONTENT)
async def leave_party(member: AccountMember, user: SignedInUser, session: SessionDep) -> Response:
    """Queue the member's withdrawal, as their withdrawal link does, and sign them out."""
    code = member.withdraw_code
    if code is None:
        code = new_withdraw_code()
        await session.execute(
            update(PartyMember).where(PartyMember.id == member.id).values(withdraw_code=code)
        )
    membership.request_withdraw(session, code)
    await sign_out(session, user.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
