"""A party member's own account: their details, their volunteering, and leaving the party."""

from fastapi import APIRouter, Response, status
from sqlalchemy import update

from backend.api.deps import AccountMember, SessionDep, SignedInUser, account_member
from backend.models import (
    PartyMember,
    VolunteerStatus,
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
    return _read(await account_member(session, user))


@router.post("/volunteer/stop/", response_model=AccountRead)
async def stop_volunteering(
    member: AccountMember, user: SignedInUser, session: SessionDep
) -> AccountRead:
    """Stop volunteering and stay a member."""
    await volunteers.own_stop(session, member, actor=user)
    await session.commit()
    return _read(await account_member(session, user))


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
