"""A campaign's volunteers: the move table, the register, sign-up and withdrawal."""

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from backend.models import Campaign, RegistrationCentre, User, VolunteerProfile, VolunteerStatus
from backend.schemas.candidates import CampaignVolunteerUpdate, CandidateVolunteerCreate
from backend.services.audit import record
from backend.services.consent import CAMPAIGN_VOLUNTEER_WORDING
from backend.services.errors import NotFound, Refused
from backend.services.permissions import Area
from backend.services.sms import normalise_phone
from backend.services.targets import wards_in_area

V = VolunteerStatus

VOLUNTEER_MOVES: dict[VolunteerStatus, frozenset[VolunteerStatus]] = {
    V.INTERESTED: frozenset({V.ACTIVE, V.WITHDRAWN}),
    V.ACTIVE: frozenset({V.INACTIVE, V.WITHDRAWN}),
    V.INACTIVE: frozenset({V.ACTIVE, V.WITHDRAWN}),
    V.WITHDRAWN: frozenset({V.INTERESTED}),
}

OFFICER_TARGETS = frozenset({V.ACTIVE, V.INACTIVE})

PLACES = (
    selectinload(VolunteerProfile.ward),
    selectinload(VolunteerProfile.registration_centre),
)


def check_move(frm: VolunteerStatus, to: VolunteerStatus) -> None:
    """Refuse a move the table does not list."""
    if to not in VOLUNTEER_MOVES[frm]:
        raise Refused(f"A {frm.label.lower()} volunteer cannot be moved to {to.label.lower()}.")


async def write_status(
    session: AsyncSession, profile: VolunteerProfile, old: VolunteerStatus, **values
) -> None:
    """Write the change only if the row still has the status it was checked against."""
    changed = await session.execute(
        update(VolunteerProfile)
        .where(VolunteerProfile.id == profile.id, VolunteerProfile.status == old)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise Refused("This volunteer's status changed meanwhile; reload and try again.")
    for name, value in values.items():
        set_committed_value(profile, name, value)


def audit(
    session: AsyncSession,
    profile: VolunteerProfile,
    action: str,
    detail: dict,
    *,
    actor: User | None = None,
    actor_name: str = "public",
) -> None:
    record(
        session,
        actor=actor,
        actor_name=actor_name,
        action=action,
        subject_type="volunteer_profile",
        subject_id=profile.id,
        detail=detail,
    )


async def volunteers(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    *,
    q: str = "",
    ward: uuid.UUID | None = None,
    status: VolunteerStatus | None = None,
    area: Area | None = None,
) -> list[VolunteerProfile]:
    """The campaign's volunteers in the area (None for all), newest first, by name or phone,
    ward and status."""
    statement = (
        select(VolunteerProfile)
        .where(VolunteerProfile.campaign_id == campaign_id)
        .options(*PLACES)
        .order_by(VolunteerProfile.created_at.desc())
    )
    if q.strip():
        like = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                (VolunteerProfile.first_name + " " + VolunteerProfile.last_name).ilike(like),
                VolunteerProfile.phone.ilike(like),
            )
        )
    if ward:
        statement = statement.where(VolunteerProfile.ward_id == ward)
    if status:
        statement = statement.where(VolunteerProfile.status == status)
    if area is not None:
        statement = statement.where(
            area.where(VolunteerProfile.ward_id, VolunteerProfile.registration_centre_id)
        )
    return list(await session.scalars(statement))


async def update_volunteer(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    volunteer_id: uuid.UUID,
    payload: CampaignVolunteerUpdate,
    *,
    actor: User,
    area: Area | None = None,
) -> VolunteerProfile:
    """Make one of the campaign's volunteers in the area (None for all) active or inactive and
    edit the notes, audited."""
    profile = await session.scalar(
        select(VolunteerProfile).where(
            VolunteerProfile.id == volunteer_id, VolunteerProfile.campaign_id == campaign_id
        )
    )
    if profile is None or (
        area is not None and not area.holds(profile.ward_id, profile.registration_centre_id)
    ):
        raise NotFound("No such volunteer.")
    if profile.erased_at is not None:
        raise Refused("This person's details were erased.")
    if payload.status is not None:
        to = VolunteerStatus(payload.status)
        if to not in OFFICER_TARGETS:
            raise Refused("An officer can only make a volunteer active or inactive.")
        old = profile.status
        check_move(old, to)
        await write_status(session, profile, old, status=to)
        audit(
            session, profile, "volunteer.status", {"from": old.value, "to": to.value}, actor=actor
        )
    if "availability_notes" in payload.model_fields_set:
        profile.availability_notes = payload.availability_notes
        audit(session, profile, "volunteer.notes", {}, actor=actor)
    await session.commit()
    return await session.scalar(
        select(VolunteerProfile)
        .where(VolunteerProfile.id == volunteer_id)
        .options(*PLACES)
        .execution_options(populate_existing=True)
    )


async def sign_up(
    session: AsyncSession, campaign: Campaign, payload: CandidateVolunteerCreate
) -> str:
    """Add a volunteer to the campaign; a phone already there is left as it is.

    Returns a withdrawal code either way, a working one only for a new volunteer.
    """
    if campaign.closed_at is not None:
        raise Refused("This campaign has closed.")
    phone = normalise_phone(payload.phone)
    if phone is None:
        raise Refused("Enter a Kenyan mobile number, like 0712 345678.")
    if payload.ward not in {w.id for w in await wards_in_area(session, campaign)}:
        raise Refused("Pick a ward inside the seat this candidate is vying for.")
    centre_ward = await session.scalar(
        select(RegistrationCentre.ward_id).where(
            RegistrationCentre.id == payload.registration_centre
        )
    )
    if centre_ward != payload.ward:
        raise Refused("Pick a polling station in the ward you chose.")
    code = secrets.token_urlsafe(18)
    known = await session.scalar(
        select(VolunteerProfile.id).where(
            VolunteerProfile.campaign_id == campaign.id, VolunteerProfile.phone == phone
        )
    )
    if known is None:
        session.add(
            VolunteerProfile(
                campaign_id=campaign.id,
                first_name=payload.first_name,
                last_name=payload.last_name,
                phone=phone,
                email=payload.email,
                ward_id=payload.ward,
                registration_centre_id=payload.registration_centre,
                profession=payload.profession,
                profession_other=payload.profession_other,
                interests=[a.value for a in payload.areas],
                interest_other=payload.area_other,
                preferred_contact=payload.preferred_contact,
                consent_wording=CAMPAIGN_VOLUNTEER_WORDING,
                consent_at=datetime.now(UTC),
                withdraw_code=code,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()  # the same phone signed up a moment ago
    return code


async def withdraw(session: AsyncSession, code: str) -> None:
    """Delete the campaign volunteer this code belongs to; nothing for any other code."""
    await session.execute(
        delete(VolunteerProfile).where(
            VolunteerProfile.withdraw_code == code, VolunteerProfile.campaign_id.is_not(None)
        )
    )
    await session.commit()
