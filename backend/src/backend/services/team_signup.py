"""Mobilizers and agents signing themselves up on a workspace's team link, and the queue the
candidate, manager and coordinators decide.

A sign-up makes a pending login that cannot sign in. Approval activates it, puts the person on
the workspace as a mobilizer or agent, and emails an invite link; rejection deletes the login.
"""

import re
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    Agent,
    Campaign,
    FieldRole,
    LinkPurpose,
    OperationalGrain,
    RegistrationCentre,
    RegistrationStatus,
    Target,
    TeamRegistration,
    User,
    UserRole,
)
from backend.security import new_short_code
from backend.services.accounts import (
    add_member,
    add_mobilizer,
    clean_email,
    new_login,
    sign_out,
    unit_holder,
    user_with_email,
)
from backend.services.audit import record
from backend.services.errors import NotFound, Refused
from backend.services.login_links import send_link
from backend.services.permissions import Area, narrow
from backend.services.sms import require_phone
from backend.services.targets import ward_in_area

CONSENT_VERSION = "team-1"
CONSENT = (
    "I agree that this campaign may keep my name, phone, email, ID number and the place I "
    "work, to vet me, contact me and pay me. Only the candidate and the campaign manager see "
    "my ID number. I can ask for my details to be erased."
)
SIGNED_UP = (
    "Thank you. The campaign will review your sign-up; once approved you get an email with a "
    "link to choose your password."
)
WITH_PLACES = (
    selectinload(TeamRegistration.ward),
    selectinload(TeamRegistration.registration_centre),
)


async def by_code(session: AsyncSession, code: str) -> Campaign:
    campaign = await session.scalar(select(Campaign).where(Campaign.team_code == code))
    if campaign is None:
        raise NotFound("This team sign-up link is not valid.")
    return campaign


async def centres_of(session: AsyncSession, campaign: Campaign, ward_id: uuid.UUID) -> list:
    """The registration centres of a ward inside the workspace's seat, by name."""
    if not await ward_in_area(session, campaign, ward_id):
        raise Refused("That ward is not one this campaign works.")
    found = await session.scalars(
        select(RegistrationCentre)
        .where(RegistrationCentre.ward_id == ward_id, RegistrationCentre.retired.is_(False))
        .order_by(RegistrationCentre.name)
    )
    return list(found)


async def _place(session: AsyncSession, campaign: Campaign, details: dict) -> tuple:
    """The ward and centre a sign-up names, checked against the workspace's seat."""
    role, ward_id, centre_id = (
        details["role"],
        details.get("ward"),
        details.get("registration_centre"),
    )
    wants_centre = role is FieldRole.AGENT or campaign.operational_grain is OperationalGrain.CENTRE
    if not wants_centre:
        if ward_id is None or not await ward_in_area(session, campaign, ward_id):
            raise Refused("Pick a ward this campaign works.")
        return ward_id, None
    centre = await session.get(RegistrationCentre, centre_id) if centre_id else None
    if centre is None or not await ward_in_area(session, campaign, centre.ward_id):
        raise Refused("Pick a registration centre this campaign works.")
    if role is FieldRole.MOBILIZER:
        targeted = await session.scalar(
            select(Target.id).where(
                Target.campaign_id == campaign.id, Target.registration_centre_id == centre.id
            )
        )
        if targeted is None:
            raise Refused("Pick a registration centre this campaign works.")
    return centre.ward_id, centre.id


async def _username(session: AsyncSession, email: str) -> str:
    stem = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower())[:30] or "team"
    return f"{stem}-{secrets.token_hex(3)}"


async def register(session: AsyncSession, campaign: Campaign, details: dict) -> None:
    """Record a sign-up and its pending login; refused when its phone, ID number or email is
    already taken."""
    if not details["consent_given"]:
        raise Refused("Tick the consent box to sign up.")
    phone = require_phone(details["phone"], "Give a phone number like 0712 345678.")
    email = clean_email(details["email"])
    if "@" not in email:
        raise Refused("Give your email address: you sign in with it.")
    ward_id, centre_id = await _place(session, campaign, details)
    id_number = details["id_number"].upper()
    taken = await session.scalar(
        select(TeamRegistration).where(
            TeamRegistration.campaign_id == campaign.id,
            TeamRegistration.status != RegistrationStatus.REJECTED,
            or_(TeamRegistration.phone == phone, TeamRegistration.id_number == id_number),
        )
    )
    if taken is not None:
        what = "phone number" if taken.phone == phone else "ID number"
        raise Refused(f"That {what} is already signed up to this team.")
    if await user_with_email(session, email) is not None:
        raise Refused("That email already has a login. Sign in, or use Forgot your password.")
    try:
        user, _ = await new_login(
            session,
            username=await _username(session, email),
            role=UserRole(details["role"].value),
            password=secrets.token_urlsafe(32),
            first_name=details["first_name"],
            last_name=details["last_name"],
            email=email,
            phone=phone,
        )
        user.is_active, user.pending = False, True
        registration = TeamRegistration(
            campaign_id=campaign.id,
            user_id=user.id,
            role=details["role"],
            first_name=details["first_name"],
            last_name=details["last_name"],
            phone=phone,
            email=email,
            id_number=id_number,
            ward_id=ward_id,
            registration_centre_id=centre_id,
            consent_wording=CONSENT,
            consent_version=CONSENT_VERSION,
        )
        session.add(registration)
        await session.flush()
        record(
            session,
            actor=None,
            action="team.register",
            subject_type="team_registration",
            subject_id=registration.id,
            campaign_id=campaign.id,
            detail={"role": details["role"].value},
        )
        await session.commit()
    except IntegrityError as clash:
        await session.rollback()
        raise Refused(
            "That phone number or ID number is already signed up to this team."
        ) from clash


async def registrations(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    area: Area | None,
    status: RegistrationStatus | None,
) -> list[TeamRegistration]:
    """A workspace's sign-ups, newest first, inside `area` (None for all)."""
    statement = select(TeamRegistration).where(TeamRegistration.campaign_id == campaign_id)
    if status is not None:
        statement = statement.where(TeamRegistration.status == status)
    found = await session.scalars(
        narrow(statement, area, TeamRegistration)
        .options(*WITH_PLACES)
        .order_by(TeamRegistration.created_at.desc())
    )
    return list(found)


async def registration(
    session: AsyncSession, campaign_id: uuid.UUID, registration_id: uuid.UUID, area: Area | None
) -> TeamRegistration:
    """One sign-up the caller may decide; 404 outside their area."""
    found = await session.scalar(
        narrow(
            select(TeamRegistration).where(
                TeamRegistration.id == registration_id,
                TeamRegistration.campaign_id == campaign_id,
            ),
            area,
            TeamRegistration,
        ).options(*WITH_PLACES)
    )
    if found is None:
        raise NotFound("No such sign-up.")
    return found


async def _claim(
    session: AsyncSession, registration: TeamRegistration, outcome: RegistrationStatus
) -> None:
    """Move a pending sign-up to its outcome in one statement, so two decisions racing on it
    cannot both go through."""
    if registration.status is not RegistrationStatus.PENDING:
        raise Refused(f"This sign-up was already {registration.status.label.lower()}.")
    moved = await session.execute(
        update(TeamRegistration)
        .where(
            TeamRegistration.id == registration.id,
            TeamRegistration.status == RegistrationStatus.PENDING,
        )
        .values(status=outcome)
        .execution_options(synchronize_session=False)
    )
    if moved.rowcount != 1:
        raise Refused("This sign-up was decided a moment ago; reload to see how.")


async def approve(
    session: AsyncSession, campaign: Campaign, registration: TeamRegistration, *, actor: User
) -> tuple[str, bool]:
    """Activate the login, put it on the workspace in its role, and email an invite link.

    Returns how the invite went out and whether a mobilizer got their ward or centre: one
    already held stays with its holder, and the newcomer starts with none.
    """
    await _claim(session, registration, RegistrationStatus.APPROVED)
    user = await session.get(User, registration.user_id) if registration.user_id else None
    if user is None:
        raise Refused("This sign-up's login is gone; ask them to sign up again.")
    user.pending, user.is_active = False, True
    placed = True
    if registration.role is FieldRole.MOBILIZER:
        held = await unit_holder(
            session, campaign.id, registration.ward_id, registration.registration_centre_id
        )
        placed = held is None
        await add_mobilizer(
            session,
            campaign,
            registration.ward_id if placed else None,
            user,
            centre_id=registration.registration_centre_id if placed else None,
        )
    else:
        await add_member(session, campaign.id, user)
        session.add(
            Agent(
                campaign_id=campaign.id,
                user_id=user.id,
                ward_id=registration.ward_id,
                registration_centre_id=registration.registration_centre_id,
            )
        )
    registration.status = RegistrationStatus.APPROVED
    registration.decided_by_id, registration.decided_at = actor.id, datetime.now(UTC)
    invite = await send_link(session, user, LinkPurpose.INVITE)
    record(
        session,
        actor=actor,
        action="team.approve",
        subject_type="team_registration",
        subject_id=registration.id,
        campaign_id=campaign.id,
        detail={"role": registration.role.value, "placed": placed},
    )
    await session.commit()
    return invite, placed


async def reject(
    session: AsyncSession,
    campaign: Campaign,
    registration: TeamRegistration,
    reason: str,
    *,
    actor: User,
) -> None:
    """Refuse a sign-up with a reason: its login is deleted and its ID number blanked."""
    await _claim(session, registration, RegistrationStatus.REJECTED)
    if registration.user_id is not None:
        await sign_out(session, registration.user_id)
        await session.execute(delete(User).where(User.id == registration.user_id))
    registration.user_id = None
    registration.id_number = ""
    registration.status = RegistrationStatus.REJECTED
    registration.reason = reason
    registration.decided_by_id, registration.decided_at = actor.id, datetime.now(UTC)
    record(
        session,
        actor=actor,
        action="team.reject",
        subject_type="team_registration",
        subject_id=registration.id,
        campaign_id=campaign.id,
    )
    await session.commit()


async def replace_code(session: AsyncSession, campaign: Campaign, *, actor: User) -> str:
    """A new team link; the old one stops working."""
    campaign.team_code = new_short_code()
    record(
        session,
        actor=actor,
        action="team.replace_code",
        subject_type="campaign",
        subject_id=campaign.id,
        campaign_id=campaign.id,
    )
    await session.commit()
    return campaign.team_code
